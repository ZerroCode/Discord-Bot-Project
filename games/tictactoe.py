"""Tic-tac-toe rules and Discord views, independent of command registration."""

import asyncio
import logging

import discord

logger = logging.getLogger(__name__)
CHALLENGE_TIMEOUT = 120
GAME_TIMEOUT = 300
WINNING_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)


def check_winner(board: list[str | None]) -> str | None:
    for a, b, c in WINNING_LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
    return "Draw" if all(cell is not None for cell in board) else None


class _TimedView(discord.ui.View):
    def __init__(self, *, timeout: float, timeout_title: str):
        super().__init__(timeout=timeout)
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
                            description="Start a new game with /arcade tictactoe.",
                            color=discord.Color.greyple(),
                        ),
                        view=self,
                    )
                except discord.HTTPException:
                    logger.exception("Could not update expired game message")

    async def on_error(self, interaction, error, item) -> None:
        logger.error("Game interaction failed", exc_info=(type(error), error, error.__traceback__))
        self.close()
        try:
            message = "The game could not be updated. Please start a new challenge."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            logger.exception("Could not report game error to player")
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logger.exception("Could not disable failed game controls")


class ChallengeView(_TimedView):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=CHALLENGE_TIMEOUT, timeout_title="Challenge Expired")
        self.challenger = challenger
        self.opponent = opponent

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
        game = TicTacToeView(self.challenger, self.opponent)
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


class _CellButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.on_cell_click(interaction, self, self.index)


class TicTacToeView(_TimedView):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(timeout=GAME_TIMEOUT, timeout_title="Tic Tac Toe - Timed Out")
        self.player1 = player1
        self.player2 = player2
        self.marks = {player1.id: "X", player2.id: "O"}
        self.board: list[str | None] = [None] * 9
        self.current_turn = player1.id
        for index in range(9):
            self.add_item(_CellButton(index))

    def make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Tic Tac Toe",
            description=f"{self.player1.mention} (X) vs {self.player2.mention} (O)",
        )
        winner = check_winner(self.board)
        if winner == "Draw":
            embed.title = "Tic Tac Toe - Draw"
            embed.color = discord.Color.blurple()
        elif winner:
            member = self.player1 if winner == "X" else self.player2
            embed.title = "Tic Tac Toe - Game Over"
            embed.description = f":tada:{member.mention} ({winner}) wins!"
            embed.color = discord.Color.gold()
        else:
            player = self.player1 if self.current_turn == self.player1.id else self.player2
            embed.set_footer(text=f"Turn: {player.display_name} | Expires after 5 minutes of inactivity")
        return embed

    async def on_cell_click(self, interaction: discord.Interaction, button: discord.ui.Button, index: int) -> None:
        if interaction.user.id not in self.marks:
            await interaction.response.send_message("You're not part of this game.", ephemeral=True)
            return
        if self._lock.locked():
            await interaction.response.send_message("A move is being updated. Please try again.", ephemeral=True)
            return

        async with self._lock:
            if self.closed or self.is_finished():
                await interaction.response.send_message("This game has ended.", ephemeral=True)
                return
            if interaction.user.id != self.current_turn:
                await interaction.response.send_message("It's not your turn.", ephemeral=True)
                return
            if self.board[index] is not None:
                await interaction.response.send_message("That cell is already taken.", ephemeral=True)
                return

            mark = self.marks[interaction.user.id]
            self.board[index] = mark
            button.label = mark
            button.style = discord.ButtonStyle.primary if mark == "X" else discord.ButtonStyle.danger
            button.disabled = True
            if check_winner(self.board):
                self.close()
            else:
                self.current_turn = self.player2.id if mark == "X" else self.player1.id
            try:
                await interaction.response.edit_message(embed=self.make_embed(), view=self)
            except Exception:
                # End a session if its local state can no longer be shown on Discord.
                self.close()
                raise
