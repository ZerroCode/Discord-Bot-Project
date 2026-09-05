import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from games.arcade import Arcade
from games.connect4 import ChallengeView


class CommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cog = Arcade()
        self.challenger = Mock(spec=discord.Member, id=1, mention="<@1>", bot=False)
        self.opponent = Mock(spec=discord.Member, id=2, mention="<@2>", bot=False)
        self.event = SimpleNamespace(
            guild=object(), user=self.challenger,
            response=SimpleNamespace(send_message=AsyncMock()),
            original_response=AsyncMock(),
        )

    async def invoke(self):
        await self.cog.connect4.callback(self.cog, self.event, self.opponent)

    async def test_connect4_sends_challenge_and_tracks_message(self):
        await self.invoke()
        sent = self.event.response.send_message.call_args.kwargs
        view = sent["view"]
        self.addCleanup(view.close)
        self.assertIsInstance(view, ChallengeView)
        self.assertEqual(sent["embed"].title, "Connect 4 Challenge")
        self.assertIs(view.challenger, self.challenger)
        self.assertIs(view.opponent, self.opponent)
        self.assertIs(view.message, self.event.original_response.return_value)

    async def test_rejects_dm_self_and_bot_challenges(self):
        for invalid in ("dm", "self", "bot", "nonmember"):
            with self.subTest(invalid=invalid):
                self.setUp()
                if invalid == "dm":
                    self.event.guild = None
                elif invalid == "self":
                    self.opponent = self.challenger
                elif invalid == "bot":
                    self.opponent.bot = True
                else:
                    self.event.user = SimpleNamespace(id=1)
                await self.invoke()
                sent = self.event.response.send_message.call_args.kwargs
                self.assertTrue(sent["ephemeral"])
                self.assertNotIn("view", sent)
                self.event.original_response.assert_not_awaited()

    async def test_failed_send_or_message_lookup_stops_challenge(self):
        for fail_send in (True, False):
            self.setUp()
            failing = self.event.response.send_message if fail_send else self.event.original_response
            failing.side_effect = RuntimeError("network failure")
            with self.assertRaisesRegex(RuntimeError, "network failure"):
                await self.invoke()
            view = self.event.response.send_message.call_args.kwargs["view"]
            self.assertTrue(view.is_finished())
            self.assertTrue(all(button.disabled for button in view.children))
