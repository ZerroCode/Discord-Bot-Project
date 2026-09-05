import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from games.connect4 import (
    COLUMNS, ROWS, RED, YELLOW, ChallengeView, Connect4View, check_winner, drop_piece, new_board,
)


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


def draw_board():
    return [list(row) for row in ("RRYYRRY", "YYRRYYR") * 3]


class RulesTests(unittest.TestCase):
    def test_every_winning_line_for_both_colors(self):
        lines = 0
        for row in range(ROWS):
            for column in range(COLUMNS):
                for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                    if not (0 <= row + 3 * dr < ROWS and 0 <= column + 3 * dc < COLUMNS):
                        continue
                    lines += 1
                    for mark in (RED, YELLOW):
                        board = new_board()
                        for step in range(3):
                            board[row + step * dr][column + step * dc] = mark
                        self.assertIsNone(check_winner(board))
                        board[row + 3 * dr][column + 3 * dc] = mark
                        self.assertEqual(check_winner(board), mark)
        self.assertEqual(lines, 69)

    def test_gravity_full_column_and_invalid_input(self):
        board = new_board()
        for turn in range(ROWS):
            self.assertEqual(drop_piece(board, 3, RED if turn % 2 == 0 else YELLOW), ROWS - 1 - turn)
        before = [row.copy() for row in board]
        for column, mark in ((3, RED), (-1, RED), (7, RED), (0, "invalid")):
            with self.assertRaises(ValueError):
                drop_piece(board, column, mark)
            self.assertEqual(board, before)
        self.assertTrue(all(row[0] is None for row in board))

    def test_draw_and_winner_on_full_board(self):
        board = draw_board()
        self.assertEqual(check_winner(board), "Draw")
        board[0][:4] = [RED] * 4
        self.assertEqual(check_winner(board), RED)

    def test_edges_do_not_wrap(self):
        board = new_board()
        for row, column in ((5, 5), (5, 6), (4, 0), (4, 1)):
            board[row][column] = RED
        self.assertIsNone(check_winner(board))


class ViewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p1, self.p2 = player(1), player(2)

    def game(self):
        game = Connect4View(self.p1, self.p2)
        self.addCleanup(game.close)
        return game

    async def move(self, game, column, user=None):
        event = interaction(user or (self.p1 if game.current_turn == self.p1.id else self.p2))
        await game.children[column].callback(event)
        return event

    async def test_buttons_and_turn_display(self):
        game = self.game()
        self.assertEqual([button.label for button in game.children], list("1234567"))
        self.assertTrue(all(len(row["components"]) <= 5 for row in game.to_components()))
        self.assertEqual(game.make_embed().description.count("⚪"), 42)
        await self.move(game, 6)
        self.assertEqual(game.board[5][6], RED)
        self.assertEqual(game.current_turn, self.p2.id)
        self.assertIn(self.p2.display_name, game.make_embed().footer.text)

    async def test_win_closes_board_and_rejects_later_clicks(self):
        game = self.game()
        for column in (0, 1, 0, 1, 0, 1, 0):
            await self.move(game, column)
        self.assertEqual(check_winner(game.board), RED)
        self.assertTrue(game.is_finished())
        self.assertTrue(all(button.disabled for button in game.children))
        self.assertEqual(game.make_embed().title, "Connect 4 - Game Over")
        self.assertIn(self.p1.mention, game.make_embed().fields[0].value)
        before = [row.copy() for row in game.board]
        event = await self.move(game, 2)
        event.response.edit_message.assert_not_awaited()
        self.assertEqual(game.board, before)

    async def test_last_move_draw(self):
        game = self.game()
        game.board = draw_board()
        game.board[0][0] = None
        await self.move(game, 0)
        self.assertEqual(game.make_embed().title, "Connect 4 - Draw")
        self.assertTrue(game.is_finished())
        self.assertTrue(all(button.disabled for button in game.children))

    async def test_spectators_wrong_turn_and_full_column_are_rejected(self):
        game = self.game()
        for user in (player(3), self.p2):
            event = await self.move(game, 0, user)
            event.response.send_message.assert_awaited_once()
            self.assertTrue(event.response.send_message.call_args.kwargs["ephemeral"])
            self.assertEqual(game.board, new_board())
        for _ in range(ROWS):
            await self.move(game, 0)
        self.assertTrue(game.children[0].disabled)
        self.assertFalse(game.children[1].disabled)
        before = [row.copy() for row in game.board]
        event = await self.move(game, 0)
        event.response.edit_message.assert_not_awaited()
        self.assertEqual(game.board, before)
        self.assertEqual(game.current_turn, self.p1.id)

    async def test_overlapping_move_and_timeout(self):
        game = self.game()
        game.message = SimpleNamespace(edit=AsyncMock())
        event = interaction(self.p1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_edit(**kwargs):
            entered.set()
            await release.wait()

        event.response.edit_message.side_effect = slow_edit
        pending = asyncio.create_task(game.children[0].callback(event))
        timeout = None
        try:
            await asyncio.wait_for(entered.wait(), 1)
            rejected = await self.move(game, 1, self.p2)
            rejected.response.edit_message.assert_not_awaited()
            self.assertIsNone(game.board[5][1])
            timeout = asyncio.create_task(game.on_timeout())
            await asyncio.sleep(0)
            game.message.edit.assert_not_awaited()
        finally:
            release.set()
            await pending
            if timeout:
                await timeout
        self.assertTrue(game.is_finished())
        self.assertTrue(all(button.disabled for button in game.children))
        self.assertIn("/arcade connect4", game.message.edit.call_args.kwargs["embed"].description)

    async def test_challenge_authorization_and_competing_responses(self):
        challenge = ChallengeView(self.p1, self.p2)
        self.addCleanup(challenge.close)
        for action in (challenge.accept, challenge.decline):
            event = interaction(self.p1)
            await action.callback(event)
            event.response.edit_message.assert_not_awaited()
            self.assertFalse(challenge.closed)
        event = interaction(self.p2)
        await challenge.accept.callback(event)
        game = event.response.edit_message.call_args.kwargs["view"]
        self.addCleanup(game.close)
        self.assertIsInstance(game, Connect4View)
        self.assertIs(game.message, event.message)
        for action in (challenge.accept, challenge.decline):
            duplicate = interaction(self.p2)
            await action.callback(duplicate)
            duplicate.response.edit_message.assert_not_awaited()

    async def test_decline_and_timeout_prevent_accept(self):
        for expire in (False, True):
            challenge = ChallengeView(self.p1, self.p2)
            self.addCleanup(challenge.close)
            challenge.message = SimpleNamespace(edit=AsyncMock())
            if expire:
                await challenge.on_timeout()
                self.assertIn("/arcade connect4", challenge.message.edit.call_args.kwargs["embed"].description)
            else:
                await challenge.decline.callback(interaction(self.p2))
            event = interaction(self.p2)
            await challenge.accept.callback(event)
            event.response.edit_message.assert_not_awaited()
            self.assertTrue(challenge.is_finished())

    async def test_failed_edits_close_game_and_challenge(self):
        for view in (self.game(), ChallengeView(self.p1, self.p2)):
            self.addCleanup(view.close)
            event = interaction(self.p2 if isinstance(view, ChallengeView) else self.p1)
            event.response.edit_message.side_effect = RuntimeError("network failure")
            with self.assertRaisesRegex(RuntimeError, "network failure"):
                await view.children[0].callback(event)
            self.assertTrue(view.is_finished())
            self.assertTrue(event.response.edit_message.call_args.kwargs["view"].is_finished())
