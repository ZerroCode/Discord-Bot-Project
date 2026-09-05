"""Read configuration once; environment variables take precedence over .env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str = field(repr=False)
    guild_id: int | None = None


def load_config() -> Config:
    load_dotenv(Path(__file__).parent / ".env", override=False)
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise ValueError("DISCORD_TOKEN is required. Set it in the environment or .env.")

    raw_guild_id = os.getenv("DISCORD_GUILD_ID", "").strip()
    guild_id = None
    if raw_guild_id:
        try:
            guild_id = int(raw_guild_id)
        except ValueError:
            raise ValueError("DISCORD_GUILD_ID must be a positive integer or left empty.") from None
        if not 0 < guild_id < 2**64:
            raise ValueError("DISCORD_GUILD_ID must be a valid positive Discord ID.")

    return Config(token=token, guild_id=guild_id)
