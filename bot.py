"""Bot lifecycle and command synchronization."""

import logging

import discord
from discord.ext import commands

from config import Config

logger = logging.getLogger(__name__)
EXTENSIONS = ("games.arcade",)


class GameBot(commands.Bot):
    def __init__(self, config: Config):
        # Slash commands and buttons don't need member or message-content intents.
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.command_guild = (
            discord.Object(id=config.guild_id) if config.guild_id is not None else None
        )

    async def setup_hook(self) -> None:
        for extension in EXTENSIONS:
            await self.load_extension(extension)
        synced = await self.tree.sync(guild=self.command_guild)
        scope = f"guild {self.command_guild.id}" if self.command_guild else "global"
        logger.info("Synced %d command groups (%s)", len(synced), scope)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user)
