"""The single owner of /arcade; add new game commands to this cog."""

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from games.tictactoe import ChallengeView

if TYPE_CHECKING:
    from bot import GameBot


@app_commands.guild_only()
class Arcade(commands.GroupCog, group_name="arcade", group_description="Arcade games"):
    @app_commands.command(description="Challenge another member to tic-tac-toe.")
    async def tictactoe(self, interaction: discord.Interaction, opponent: discord.Member) -> None:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Start games in a server.", ephemeral=True)
            return
        if opponent.bot:
            await interaction.response.send_message("You can't challenge a bot.", ephemeral=True)
            return
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You can't challenge yourself.", ephemeral=True)
            return

        view = ChallengeView(interaction.user, opponent)
        embed = discord.Embed(
            title="Tic Tac Toe Challenge",
            description=f"{interaction.user.mention} has challenged {opponent.mention} to Tic Tac Toe.",
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
