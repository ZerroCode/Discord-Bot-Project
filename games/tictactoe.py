"""Tic-tac-toe rules and Discord views, independent of command registration."""

import discord

from games.views import ChallengeView as BaseChallengeView, GAME_TIMEOUT, TimedView

COMMAND = "/arcade tictactoe"
WINNING_LINES = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)


def check_winner(board: list[str | None]) -> str | None:
    for a, b, c in WINNING_LINES:
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a]
    return "Draw" if all(cell is not None for cell in board) else None

class _CellButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.on_cell_click(interaction, self, self.index)


class TicTacToeView(TimedView):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(command=COMMAND, timeout=GAME_TIMEOUT, timeout_title="Tic Tac Toe - Timed Out")
        self.player1 = player1
        self.player2 = player2
        self.marks = {player1.id: "X", player2.id: "O"}
        self.board: list[str | None] = [None] * 9
        self.current_turn = player1.id
        for index in range(9):
            self.add_item(_CellButton(index))

    def make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Tic Tac Toe",
            description=f"{self.player1.mention} (X) vs {self.player2.mention} (O)",
        )
        winner = check_winner(self.board)
        if winner == "Draw":
            embed.title = "Tic Tac Toe - Draw"
            embed.color = discord.Color.blurple()
        elif winner:
            member = self.player1 if winner == "X" else self.player2
            embed.title = "Tic Tac Toe - Game Over"
            embed.color = discord.Color.gold()
            embed.add_field(name="Winner", value=f"🎉 {member.mention} ({winner}) wins!")
        else:
            player = self.player1 if self.current_turn == self.player1.id else self.player2
            embed.set_footer(text=f"Turn: {player.display_name} | Expires after 5 minutes of inactivity")
        return embed

    async def on_cell_click(self, interaction: discord.Interaction, button: discord.ui.Button, index: int) -> None:
        if interaction.user.id not in self.marks:
            await interaction.response.send_message("You're not part of this game.", ephemeral=True)
            return
        if self._lock.locked():
            await interaction.response.send_message("A move is being updated. Please try again.", ephemeral=True)
            return

        async with self._lock:
            if self.closed or self.is_finished():
                await interaction.response.send_message("This game has ended.", ephemeral=True)
                return
            if interaction.user.id != self.current_turn:
                await interaction.response.send_message("It's not your turn.", ephemeral=True)
                return
            if self.board[index] is not None:
                await interaction.response.send_message("That cell is already taken.", ephemeral=True)
                return

            mark = self.marks[interaction.user.id]
            self.board[index] = mark
            button.label = mark
            button.style = discord.ButtonStyle.primary if mark == "X" else discord.ButtonStyle.danger
            button.disabled = True
            if check_winner(self.board):
                self.close()
            else:
                self.current_turn = self.player2.id if mark == "X" else self.player1.id
            try:
                await interaction.response.edit_message(embed=self.make_embed(), view=self)
            except Exception:
                # End a session if its local state can no longer be shown on Discord.
                self.close()
                raise

class ChallengeView(BaseChallengeView):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(challenger, opponent, command=COMMAND)

    def create_game(self) -> TicTacToeView:
        return TicTacToeView(self.challenger, self.opponent)
