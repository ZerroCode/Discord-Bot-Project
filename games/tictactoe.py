import os
import discord
from discord import app_commands

# Guild ID for command registration (use guild-based commands for faster sync)
GUILD_ID = None
if os.getenv('DISCORD_GUILD_ID'):
    try:
        GUILD_ID = discord.Object(id=int(os.getenv('DISCORD_GUILD_ID')))
    except Exception:
        GUILD_ID = None


class ChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=None)
        self.challenger = challenger
        self.opponent = opponent

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only the challenged user may accept
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged user can accept.", ephemeral=True)
            return

        # Acknowledge the interaction quickly so Discord doesn't mark it failed
        await interaction.response.send_message("Starting the game…", ephemeral=True)

        # Disable the challenge buttons
        for child in self.children:
            child.disabled = True

        # Edit the original message to show accepted (edit the message object directly)
        embed = discord.Embed(
            title="Challenge Accepted",
            description=f"{self.opponent.mention} accepted the challenge from {self.challenger.mention}.",
            color=discord.Color.green(),
        )
        try:
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            # If editing via the message object fails, try editing via the interaction response as a fallback
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                # give up editing silently; the ephemeral ack was already sent
                pass

        # Send the game board using the most reliable channel available
        game_embed = discord.Embed(title="Tic Tac Toe", description=f"{self.challenger.mention} vs {self.opponent.mention}")
        view = TicTacToeView(self.challenger, self.opponent)

        send_success = False
        exceptions = []

        # Try interaction.channel first (preferred), then the original message's channel, then DM as a last resort
        possible_channels = [getattr(interaction, 'channel', None), getattr(interaction.message, 'channel', None)]
        for ch in possible_channels:
            if ch is None:
                continue
            try:
                await ch.send(embed=game_embed, view=view)
                send_success = True
                break
            except Exception as e:
                exceptions.append(e)

        if not send_success:
            try:
                dm = await interaction.user.create_dm()
                await dm.send(embed=game_embed, view=view)
                send_success = True
            except Exception as e:
                exceptions.append(e)

        if not send_success:
            # Try interaction.followup as a last programmatic attempt
            try:
                await interaction.followup.send(embed=game_embed, view=view)
                send_success = True
            except Exception as e:
                exceptions.append(e)

        if not send_success:
            # Log exceptions to console so the operator can inspect discord.log or the terminal
            print("TicTacToe: failed to send game board; exceptions:")
            for ex in exceptions:
                print(ex)
            # Notify the accepter ephemeral that creation failed
            try:
                await interaction.followup.send("Failed to create the game board. Check the bot logs.", ephemeral=True)
            except Exception:
                pass

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Only the challenged user may decline
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Only the challenged user can decline.", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="Challenge Declined",
            description=f"{self.opponent.mention} declined the challenge from {self.challenger.mention}.",
            color=discord.Color.red(),
        )
        await interaction.response.edit_message(embed=embed, view=self)


class TicTacToeView(discord.ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(timeout=None)
        self.player1 = player1
        self.player2 = player2
        # player1 is X, player2 is O
        self.marks = {player1.id: "X", player2.id: "O"}
        self.board = [None] * 9
        self.current_turn = player1.id

        # Create 9 buttons and add them to the view
        for i in range(9):
            # Use a zero-width space as an initial non-empty label so Discord validation passes
            button = discord.ui.Button(style=discord.ButtonStyle.secondary, label="\u200b", row=i // 3)
            # attach an index to the button for callback
            button.index = i
            # Create a single-argument callback (Discord passes only the interaction)
            def make_callback(index, btn):
                async def callback(interaction: discord.Interaction):
                    try:
                        await self.on_cell_click(interaction, btn, index)
                    except Exception as e:
                        # Ensure we always respond to the interaction to avoid the "didn't respond in time" message
                        print(f"TicTacToe: exception in cell callback: {e}")
                        try:
                            await interaction.response.send_message("An error occurred while handling the move.", ephemeral=True)
                        except Exception:
                            pass
                return callback

            button.callback = make_callback(i, button)
            self.add_item(button)

    async def on_cell_click(self, interaction: discord.Interaction, button: discord.ui.Button, index: int):
        # Only the two players can interact
        if interaction.user.id not in (self.player1.id, self.player2.id):
            await interaction.response.send_message("You're not part of this game.", ephemeral=True)
            return

        # Enforce turn order
        if interaction.user.id != self.current_turn:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return

        # If cell already taken, ignore
        if self.board[index] is not None:
            await interaction.response.send_message("That cell is already taken.", ephemeral=True)
            return

        mark = self.marks[interaction.user.id]
        self.board[index] = mark
        # Set button color: X -> blue (primary), O -> red (danger)
        if mark == "X":
            button.style = discord.ButtonStyle.primary
        else:
            button.style = discord.ButtonStyle.danger
        button.label = mark
        button.disabled = True

        # Check for win/draw
        winner = self.check_winner()
        embed = discord.Embed(title="Tic Tac Toe", description=f"{self.player1.mention} vs {self.player2.mention}")

        if winner:
            # Disable all buttons
            for child in self.children:
                child.disabled = True

            if winner == "Draw":
                embed.title = "Tic Tac Toe - Draw"
                embed.color = discord.Color.blurple()
                embed.description = f"It's a draw between {self.player1.mention} and {self.player2.mention}."
            else:
                winner_member = self.player1 if winner == "X" else self.player2
                embed.title = "Tic Tac Toe - Game Over"
                embed.color = discord.Color.gold()
                embed.description = f"{winner_member.mention} ({winner}) wins!"

            await interaction.response.edit_message(embed=embed, view=self)
            return

        # Switch turn
        self.current_turn = self.player1.id if self.current_turn == self.player2.id else self.player2.id

        # Update footer to show whose turn
        current_player = self.player1 if self.current_turn == self.player1.id else self.player2
        embed.set_footer(text=f"Turn: {current_player.display_name}")

        await interaction.response.edit_message(embed=embed, view=self)

    def check_winner(self):
        b = self.board
        lines = (
            (0, 1, 2),
            (3, 4, 5),
            (6, 7, 8),
            (0, 3, 6),
            (1, 4, 7),
            (2, 5, 8),
            (0, 4, 8),
            (2, 4, 6),
        )
        for a, c, d in lines:
            if b[a] and b[a] == b[c] == b[d]:
                return b[a]
        if all(x is not None for x in b):
            return "Draw"
        return None


async def setup(bot: discord.Bot | discord.Client | discord.ext.commands.Bot):
    # Register the arcade group + tictactoe command under it
    arcade = app_commands.Group(name="arcade", description="Arcade games")

    @arcade.command(name="tictactoe")
    async def tictactoe(interaction: discord.Interaction, opponent: discord.Member):
        challenger = interaction.user
        if opponent.bot:
            await interaction.response.send_message("You can't challenge a bot.", ephemeral=True)
            return
        if opponent.id == challenger.id:
            await interaction.response.send_message("You can't challenge yourself.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Tic Tac Toe Challenge",
            description=f"{challenger.mention} has challenged {opponent.mention} to a game of Tic Tac Toe.",
            color=discord.Color.blurple(),
        )

        view = ChallengeView(challenger, opponent)
        await interaction.response.send_message(embed=embed, view=view)

    # Add the group to the bot's command tree for the configured guild (if present)
    if GUILD_ID:
        bot.tree.add_command(arcade, guild=GUILD_ID)
    else:
        bot.tree.add_command(arcade)
