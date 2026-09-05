"""Shared challenge and timeout lifecycle for arcade games."""

import asyncio
import logging

import discord

CHALLENGE_TIMEOUT = 120
GAME_TIMEOUT = 300


class TimedView(discord.ui.View):
    def __init__(self, *, command: str, timeout: float, timeout_title: str):
        super().__init__(timeout=timeout)
        self.command = command
        self.message: discord.Message | discord.InteractionMessage | None = None
        self.closed = False
        self.timeout_title = timeout_title
        self._lock = asyncio.Lock()

    def close(self) -> None:
        self.closed = True
        for child in self.children:
            child.disabled = True
        self.stop()

    async def on_timeout(self) -> None:
        # Wait for an in-flight move so a stale board cannot overwrite a timeout.
        async with self._lock:
            if self.closed:
                return
            self.close()
            if self.message is not None:
                try:
                    await self.message.edit(
                        embed=discord.Embed(
                            title=self.timeout_title,
                            description=f"Start a new game with {self.command}.",
                            color=discord.Color.greyple(),
                        ),
                        view=self,
                    )
                except discord.HTTPException:
                    logging.getLogger(type(self).__module__).exception("Could not update expired game message")

    async def on_error(self, interaction, error, item) -> None:
        logging.getLogger(type(self).__module__).error("Game interaction failed", exc_info=(type(error), error, error.__traceback__))
        self.close()
        try:
            message = "The game could not be updated. Please start a new challenge."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logging.getLogger(type(self).__module__).exception("Could not report game error to player")
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logging.getLogger(type(self).__module__).exception("Could not disable failed game controls")


class ChallengeView(TimedView):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, *, command: str):
        super().__init__(command=command, timeout=CHALLENGE_TIMEOUT, timeout_title="Challenge Expired")
        self.challenger = challenger
        self.opponent = opponent

    def create_game(self):
        raise NotImplementedError

    async def _claim(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged user can respond.", ephemeral=True)
            return False
        if self.closed or self.is_finished():
            await interaction.response.send_message("This challenge has already ended.", ephemeral=True)
            return False
        # Reserve before any network await, including competing Accept/Decline clicks.
        self.close()
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._claim(interaction):
            return
        game = self.create_game()
        game.message = interaction.message
        try:
            await interaction.response.edit_message(embed=game.make_embed(), view=game)
        except Exception:
            game.close()
            raise

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self._claim(interaction):
            return
        embed = discord.Embed(
            title="Challenge Declined",
            description=f"{self.opponent.mention} declined {self.challenger.mention}'s challenge.",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=self)


