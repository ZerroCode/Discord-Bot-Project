"""Start the arcade bot with validated configuration and rotating logs."""

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from bot import GameBot
from config import load_config


def configure_logging() -> None:
    handler = RotatingFileHandler(
        Path(__file__).parent / "discord.log",
        maxBytes=5_000_000,
        backupCount=2,
        encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s",
        handlers=[handler, logging.StreamHandler()],
        force=True,
    )


async def main() -> None:
    config = load_config()
    configure_logging()
    async with GameBot(config) as client:
        await client.start(config.token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
