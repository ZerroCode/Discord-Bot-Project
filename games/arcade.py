"""The single owner of /arcade; add new game commands to this cog."""

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from games.tictactoe import ChallengeView as TicTacToeChallengeView
from games.connect4 import ChallengeView as Connect4ChallengeView
from games.views import ChallengeView as BaseChallengeView

if TYPE_CHECKING:
    from bot import GameBot


@app_commands.guild_only()
class Arcade(commands.GroupCog, group_name="arcade", group_description="Arcade games"):
    @app_commands.command(description="Challenge another member to tic-tac-toe.")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        await self._challenge(interaction, opponent, TicTacToeChallengeView, "Tic Tac Toe")

    @app_commands.command(description="Challenge another member to Connect 4.")
    async def connect4(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        await self._challenge(interaction, opponent, Connect4ChallengeView, "Connect 4")

    async def _challenge(
        self, interaction: discord.Interaction, opponent: discord.Member,
        view_type: type[BaseChallengeView], game_name: str,
    ) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Start games in a server.", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("You can't challenge a bot.", ephemeral=True)
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You can't challenge yourself.", ephemeral=True)
            return

        view = view_type(interaction.user, opponent)
        embed = discord.Embed(
            title=f"{game_name} Challenge",
            description=f"{interaction.user.mention} has challenged {opponent.mention} to {game_name}.",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="Challenge expires after 2 minutes.")
        try:
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
        except Exception:
            view.close()
            raise


async def setup(bot: "GameBot") -> None:
    if bot.command_guild is None:
        await bot.add_cog(Arcade())
    else:
        await bot.add_cog(Arcade(), guild=bot.command_guild)
