import unittest
from unittest.mock import AsyncMock, patch

from bot import GameBot
from config import Config


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_and_sync_use_same_scope(self):
        for guild_id in (None, 123):
            with self.subTest(guild_id=guild_id):
                async with GameBot(Config(token="test", guild_id=guild_id)) as bot:
                    with patch.object(bot.tree, "sync", new_callable=AsyncMock, return_value=[]) as sync:
                        await bot.setup_hook()
                        sync.assert_awaited_once_with(guild=bot.command_guild)
                        group = bot.tree.get_command("arcade", guild=bot.command_guild)
                        self.assertIsNotNone(group)
                        self.assertTrue(group.guild_only)
                        self.assertIsNotNone(group.get_command("tictactoe"))
                        self.assertIsNotNone(group.get_command("connect4"))
                        if guild_id is not None:
                            self.assertIsNone(bot.tree.get_command("arcade"))
                        await bot.on_ready()
                        await bot.on_ready()
                        sync.assert_awaited_once()

    async def test_extension_reload_does_not_duplicate_arcade(self):
        for guild_id in (None, 123):
            with self.subTest(guild_id=guild_id):
                async with GameBot(Config(token="test", guild_id=guild_id)) as bot:
                    await bot.load_extension("games.arcade")
                    await bot.reload_extension("games.arcade")
                    self.assertEqual(len(bot.tree.get_commands(guild=bot.command_guild)), 1)

    async def test_no_privileged_intents_or_unused_prefix_commands(self):
        async with GameBot(Config(token="test")) as bot:
            self.assertFalse(bot.intents.members)
            self.assertFalse(bot.intents.message_content)
            self.assertEqual(bot.commands, set())
