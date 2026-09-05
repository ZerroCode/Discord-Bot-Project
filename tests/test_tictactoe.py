import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord

from games.tictactoe import ChallengeView, TicTacToeView, check_winner


def player(user_id):
    return SimpleNamespace(id=user_id, mention=f"<@{user_id}>", display_name=f"Player {user_id}")


def interaction(user):
    return SimpleNamespace(
        user=user,
        response=SimpleNamespace(
            send_message=AsyncMock(), edit_message=AsyncMock(), is_done=Mock(return_value=False),
        ),
        followup=SimpleNamespace(send=AsyncMock()),
        message=SimpleNamespace(edit=AsyncMock()),
    )


class WinnerTests(unittest.TestCase):
    def test_all_reachable_boards(self):
        seen = set()

        def visit(board, turn):
            key = tuple(board)
            if key in seen:
                return
            seen.add(key)
            rows = [board[i:i + 3] for i in (0, 3, 6)]
            lines = rows + list(zip(*rows)) + [board[::4], board[2:7:2]]
            expected = next(
                (line[0] for line in lines if line[0] is not None and len(set(line)) == 1), None,
            )
            if expected is None and None not in board:
                expected = "Draw"
            self.assertEqual(check_winner(board), expected, board)
            if expected is not None:
                return
            for index, cell in enumerate(board):
                if cell is None:
                    changed = board.copy()
                    changed[index] = turn
                    visit(changed, "O" if turn == "X" else "X")

        visit([None] * 9, "X")
        self.assertEqual(len(seen), 5478)


class ViewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p1, self.p2 = player(1), player(2)

    def view(self):
        view = TicTacToeView(self.p1, self.p2)
        self.addCleanup(view.close)
        return view

    async def move(self, game, index, user):
        event = interaction(user)
        await game.children[index].callback(event)
        return event

    async def test_accept_twice_creates_one_board(self):
        challenge = ChallengeView(self.p1, self.p2)
        first, second = interaction(self.p2), interaction(self.p2)
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_edit(**kwargs):
            entered.set()
            await release.wait()

        first.response.edit_message.side_effect = slow_edit
        pending = asyncio.create_task(challenge.accept.callback(first))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            await challenge.accept.callback(second)
        finally:
            release.set()
            await pending
        first.response.edit_message.assert_awaited_once()
        second.response.edit_message.assert_not_awaited()
        second.response.send_message.assert_awaited_once()
        self.assertTrue(challenge.is_finished())
        game = first.response.edit_message.call_args.kwargs["view"]
        self.addCleanup(game.close)
        self.assertIsInstance(game, TicTacToeView)
        self.assertIs(game.message, first.message)
        self.assertIn(self.p1.display_name, game.make_embed().footer.text)

    async def test_decline_prevents_later_accept(self):
        challenge = ChallengeView(self.p1, self.p2)
        await challenge.decline.callback(interaction(self.p2))
        event = interaction(self.p2)
        await challenge.accept.callback(event)
        event.response.edit_message.assert_not_awaited()
        self.assertTrue(challenge.is_finished())

    async def test_only_opponent_can_resolve_challenge(self):
        challenge = ChallengeView(self.p1, self.p2)
        self.addCleanup(challenge.close)
        for action in (challenge.accept, challenge.decline):
            event = interaction(self.p1)
            await action.callback(event)
            event.response.edit_message.assert_not_awaited()
            self.assertFalse(challenge.closed)

    async def test_win_stops_view_and_rejects_queued_move(self):
        game = self.view()
        for index, user in [(0, self.p1), (3, self.p2), (1, self.p1), (4, self.p2), (2, self.p1)]:
            await self.move(game, index, user)
        self.assertTrue(game.is_finished())
        self.assertTrue(all(button.disabled for button in game.children))
        self.assertEqual(game.make_embed().title, "Tic Tac Toe - Game Over")
        board = game.board.copy()
        await self.move(game, 5, self.p1)
        self.assertEqual(game.board, board)

    async def test_draw_stops_view(self):
        game = self.view()
        for turn, index in enumerate((0, 1, 2, 4, 3, 5, 7, 6, 8)):
            await self.move(game, index, self.p1 if turn % 2 == 0 else self.p2)
        self.assertTrue(game.is_finished())
        self.assertEqual(game.make_embed().title, "Tic Tac Toe - Draw")

    async def test_invalid_moves_do_not_change_board(self):
        game = self.view()
        await self.move(game, 0, player(3))
        await self.move(game, 0, self.p2)
        self.assertEqual(game.board, [None] * 9)
        await self.move(game, 0, self.p1)
        event = await self.move(game, 0, self.p2)
        self.assertEqual(game.board, ["X"] + [None] * 8)
        self.assertEqual(game.current_turn, self.p2.id)
        event.response.edit_message.assert_not_awaited()

    async def test_overlapping_move_is_rejected_until_edit_finishes(self):
        game = self.view()
        event = interaction(self.p1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_edit(**kwargs):
            entered.set()
            await release.wait()

        event.response.edit_message.side_effect = slow_edit
        pending = asyncio.create_task(game.children[0].callback(event))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            rejected = await self.move(game, 1, self.p2)
            rejected.response.edit_message.assert_not_awaited()
            self.assertIsNone(game.board[1])
        finally:
            release.set()
            await pending
        await self.move(game, 1, self.p2)
        self.assertEqual(game.board[1], "O")

    async def test_timeout_disables_and_stops_both_views(self):
        for view in (ChallengeView(self.p1, self.p2), self.view()):
            view.message = SimpleNamespace(edit=AsyncMock())
            self.assertIsNotNone(view.timeout)
            await view.on_timeout()
            self.assertTrue(view.is_finished())
            self.assertTrue(all(button.disabled for button in view.children))
            view.message.edit.assert_awaited_once()
            event = interaction(self.p2 if isinstance(view, ChallengeView) else self.p1)
            if isinstance(view, ChallengeView):
                await view.accept.callback(event)
            else:
                await view.children[0].callback(event)
            event.response.edit_message.assert_not_awaited()

    async def test_timeout_does_not_overwrite_finished_game(self):
        game = self.view()
        game.message = SimpleNamespace(edit=AsyncMock())
        game.close()
        await game.on_timeout()
        game.message.edit.assert_not_awaited()

    async def test_failed_move_edit_stops_game(self):
        game = self.view()
        event = interaction(self.p1)
        event.response.edit_message.side_effect = RuntimeError("network failure")
        with self.assertRaisesRegex(RuntimeError, "network failure"):
            await game.children[0].callback(event)
        self.assertTrue(game.is_finished())

    async def test_failed_accept_stops_new_game(self):
        challenge = ChallengeView(self.p1, self.p2)
        event = interaction(self.p2)
        event.response.edit_message.side_effect = RuntimeError("network failure")
        with self.assertRaisesRegex(RuntimeError, "network failure"):
            await challenge.accept.callback(event)
        game = event.response.edit_message.call_args.kwargs["view"]
        self.assertTrue(game.is_finished())
        self.assertTrue(challenge.is_finished())

    async def test_error_uses_followup_after_response(self):
        game = self.view()
        event = interaction(self.p1)
        event.response.is_done.return_value = True
        with self.assertLogs("games.tictactoe", level="ERROR"):
            await game.on_error(event, RuntimeError("test error"), game.children[0])
        event.response.send_message.assert_not_awaited()
        event.followup.send.assert_awaited_once()

    async def test_deleted_message_during_timeout_is_logged(self):
        game = self.view()
        game.message = SimpleNamespace(edit=AsyncMock(side_effect=discord.NotFound(
            SimpleNamespace(status=404, reason="Not Found"), "Unknown Message",
        )))
        with self.assertLogs("games.tictactoe", level="ERROR"):
            await game.on_timeout()
        self.assertTrue(game.is_finished())
