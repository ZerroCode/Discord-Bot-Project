import discord
from discord.ext import commands
from dotenv import load_dotenv
import logging
import os
import asyncio

# Load environment variables from .env file
load_dotenv(override=True)
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = discord.Object(os.getenv('DISCORD_GUILD_ID'))

EXTENSIONS = [
    'games.tictactoe',  # Load the tictactoe extension
]

class GameBot(commands.Bot):
    async def setup_hook(self):
        for extension in EXTENSIONS:
            await self.load_extension(extension)

        await self.tree.sync()

# Configure logging to file and console
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
handler.setFormatter(formatter)

# Attach handler to discord logger (and optionally the root logger)
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO)
discord_logger.addHandler(handler)

# Also configure the root logger so other logs are captured
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create a bot instance with the specified command prefix and intents
client = GameBot(command_prefix='!', intents=intents)

# Event that runs when the bot is ready
@client.event
async def on_ready():
    print(f"Logged in as {client.user.name} - {client.user.id}")
    try:
        synced = await client.tree.sync(guild=GUILD_ID)
        print(f"Synced {len(synced)} commands for guild {GUILD_ID.id}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# run the bot
async def main():
    async with client:
        await client.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        # Already running event loop (e.g., interactive environment); schedule the task
        loop = asyncio.get_event_loop()
        loop.create_task(main())
