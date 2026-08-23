import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import random

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

EMPTY = ":white_large_square:"
X_MARK = ":regional_indicator_x:"
O_MARK = ":o2:"

player1 = None
player2 = None
turn = None
game_over = True
board = []
count = 0

winning_combinations = (
    (0, 1, 2),  # Top row
    (3, 4, 5),  # Middle row
    (6, 7, 8),  # Bottom row
    (0, 3, 6),  # Left column
    (1, 4, 7),  # Middle column
    (2, 5, 8),  # Right column
    (0, 4, 8),  # Diagonal from top-left to bottom-right
    (2, 4, 6),  # Diagonal from top-right to bottom-left
)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} - {bot.user.id}")

def render_board():
    rows = (board[index:index + 3] for index in range(0, len(board), 3))
    return "\n".join(" ".join(row) for row in rows)


def checkWinner(mark):
    return any(
        board[first] == board[second] == board[third] == mark
        for first, second, third in winning_combinations
    )

# Command to start a new game of Tic Tac Toe
@bot.command()
async def tictactoe(ctx, p1: discord.Member, p2: discord.Member):
    global count
    global player1
    global player2
    global turn
    global game_over

    if game_over:
        global board
        board = [EMPTY] * 9
        game_over = False
        count = 0
        player1 = p1
        player2 = p2

        # print the board
        await ctx.send(render_board())

        # determine who goes first
        turn = random.choice((player1, player2))
        await ctx.send(f"It is {turn.mention}'s turn.")
    else:
        await ctx.send("A game is already in progress! Finish it before starting a new one.")

# Command to place a mark on the board
@bot.command()
async def place(ctx, pos: int):
    global turn
    global player1
    global player2
    global board
    global count
    global game_over

    if not game_over:
        if turn == ctx.author:
            if turn == player1:
                mark = X_MARK
            else:
                mark = O_MARK

            if 0 < pos < 10 and board[pos - 1] == EMPTY:
                board[pos - 1] = mark
                count += 1

                # print the board
                await ctx.send(render_board())

                if checkWinner(mark):
                    game_over = True
                    await ctx.send(mark + " wins!")
                elif count >= 9:
                    game_over = True
                    await ctx.send("It's a tie!")

                # switch turns
                turn = player2 if turn == player1 else player1
            else:
                await ctx.send("Be sure to choose an integer between 1 and 9 (inclusive) and an unmarked tile.")
        else:
            await ctx.send("It is not your turn.")
    else:
        await ctx.send("Please start a new game using the !tictactoe command.")

# Error handling for commands
@tictactoe.error
async def tictactoe_error(ctx, error):
    print(error)
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please mention 2 players for this command.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Please make sure to mention/ping players (ie. <@user_id>).")

@place.error
async def place_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Please enter a position you would like to mark.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Please make sure to enter an integer.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"{ctx.author.mention}, that command does not exist.")

# Run the bot
bot.run(token, log_handler=handler, log_level=logging.DEBUG)