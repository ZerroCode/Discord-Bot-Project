import os
import unittest
from unittest.mock import patch

from config import Config, load_config


class ConfigTests(unittest.TestCase):
    def load(self, values):
        with patch.dict(os.environ, values, clear=True), patch("config.load_dotenv"):
            return load_config()

    def test_token_required(self):
        for token in ("", "   "):
            with self.subTest(token=token), self.assertRaisesRegex(ValueError, "DISCORD_TOKEN"):
                self.load({"DISCORD_TOKEN": token})

    def test_missing_guild_uses_global_commands(self):
        self.assertIsNone(self.load({"DISCORD_TOKEN": "test"}).guild_id)

    def test_empty_guild_uses_global_commands(self):
        self.assertIsNone(self.load({"DISCORD_TOKEN": "test", "DISCORD_GUILD_ID": " "}).guild_id)

    def test_valid_guild(self):
        config = self.load({"DISCORD_TOKEN": " test ", "DISCORD_GUILD_ID": " 123 "})
        self.assertEqual(config, Config(token="test", guild_id=123))

    def test_invalid_guild(self):
        for value in ("abc", "1.5", "0", "-1", str(2**64)):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "DISCORD_GUILD_ID"):
                self.load({"DISCORD_TOKEN": "test", "DISCORD_GUILD_ID": value})

    def test_token_excluded_from_repr(self):
        self.assertNotIn("secret", repr(Config(token="secret")))

    def test_dotenv_does_not_override_environment(self):
        with patch.dict(os.environ, {"DISCORD_TOKEN": "test"}, clear=True):
            with patch("config.load_dotenv") as dotenv:
                load_config()
        self.assertFalse(dotenv.call_args.kwargs["override"])
