"""Connect 4 rules and interactive Discord board."""

import discord

from games.views import ChallengeView as BaseChallengeView, GAME_TIMEOUT, TimedView

COMMAND = "/arcade connect4"
ROWS = 6
COLUMNS = 7
RED = "R"
YELLOW = "Y"
TOKENS = {None: "⚪", RED: "🔴", YELLOW: "🟡"}
COLUMN_LABELS = "1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣"


def new_board() -> list[list[str | None]]:
    return [[None] * COLUMNS for _ in range(ROWS)]


def drop_piece(board: list[list[str | None]], column: int, mark: str) -> int:
    """Drop into a zero-based column; return the landing row (top is zero)."""
    if not 0 <= column < COLUMNS:
        raise ValueError("Choose a column from 1 to 7.")
    if mark not in (RED, YELLOW):
        raise ValueError("Unknown player token.")
    for row in range(ROWS - 1, -1, -1):
        if board[row][column] is None:
            board[row][column] = mark
            return row
    raise ValueError("That column is full. Choose another column.")


def check_winner(board: list[list[str | None]]) -> str | None:
    for row in range(ROWS):
        for column in range(COLUMNS):
            mark = board[row][column]
            if mark is None:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                if not (0 <= row + 3 * dr < ROWS and 0 <= column + 3 * dc < COLUMNS):
                    continue
                if all(board[row + step * dr][column + step * dc] == mark for step in range(1, 4)):
                    return mark
    return "Draw" if all(cell is not None for row in board for cell in row) else None


class _ColumnButton(discord.ui.Button):
    def __init__(self, column: int):
        # Discord allows five buttons per action row.
        super().__init__(label=str(column + 1), style=discord.ButtonStyle.primary, row=column // 4)
        self.column = column

    async def callback(self, interaction: discord.Interaction) -> None:
        await self.view.on_column_click(interaction, self.column)


class Connect4View(TimedView):

    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(command=COMMAND, timeout=GAME_TIMEOUT, timeout_title="Connect 4 - Timed Out")
        self.player1 = player1
        self.player2 = player2
        self.marks = {player1.id: RED, player2.id: YELLOW}
        self.board = new_board()
        self.current_turn = player1.id
        for column in range(COLUMNS):
            self.add_item(_ColumnButton(column))

    def make_embed(self) -> discord.Embed:
        board = "\n".join("".join(TOKENS[cell] for cell in row) for row in self.board)
        description = f"{self.player1.mention} 🔴 vs {self.player2.mention} 🟡\n\n{board}\n{COLUMN_LABELS}"
        embed = discord.Embed(title="Connect 4", description=description, color=discord.Color.blurple())
        winner = check_winner(self.board)
        if winner == "Draw":
            embed.title = "Connect 4 - Draw"
            embed.add_field(name="Result", value="The board is full — it's a draw!")
        elif winner:
            player = self.player1 if winner == RED else self.player2
            embed.title = "Connect 4 - Game Over"
            embed.color = discord.Color.gold()
            embed.add_field(name="Winner", value=f"🎉 {player.mention} {TOKENS[winner]} wins!")
        else:
            player = self.player1 if self.current_turn == self.player1.id else self.player2
            embed.set_footer(text=f"Turn: {player.display_name} | Expires after 5 minutes of inactivity.")
        return embed

    async def on_column_click(self, interaction: discord.Interaction, column: int) -> None:
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
            try:
                drop_piece(self.board, column, self.marks[interaction.user.id])
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return
            for button in self.children:
                button.disabled = self.board[0][button.column] is not None
            if check_winner(self.board):
                self.close()
            else:
                self.current_turn = self.player2.id if self.current_turn == self.player1.id else self.player1.id
            try:
                await interaction.response.edit_message(embed=self.make_embed(), view=self)
            except Exception:
                self.close()
                raise


class ChallengeView(BaseChallengeView):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(challenger, opponent, command=COMMAND)

    def create_game(self) -> Connect4View:
        return Connect4View(self.challenger, self.opponent)
