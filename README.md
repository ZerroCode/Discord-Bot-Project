# Discord Arcade Bot

A Discord bot with challenges and interactive game boards.
Requires Python 3.10 or newer; locally tested with Python 3.14.

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `DISCORD_TOKEN` to your bot token. Optionally set
`DISCORD_GUILD_ID` to register commands in one development server. Leave it
empty to register global commands. Existing environment variables take
precedence over `.env`. Never commit the token.

Install the bot in your server with the `bot` and `applications.commands`
scopes and channel permissions to view the channel, send messages, and embed
links. This bot uses slash commands and buttons; privileged member and
message-content intents are not required.

```powershell
.\.venv\Scripts\python.exe main.py
```

Commands sync once on startup in the configured scope. Changing between guild
and global registration does not remove commands previously registered in the
other scope; remove obsolete registrations separately if switching scopes.

## Running in VS Code on Windows

Open this project folder in VS Code after creating `.venv` with the setup
commands above. Choose Run and Debug and press F5.
This configuration always starts `main.py` with the project interpreter.

If using Code Runner's **Run Code** button, open `main.py` first. The workspace
settings use `.venv\Scripts\python.exe`, bypassing the Windows Store `python`
shortcut. `bot.py` defines the bot class; it is not the startup script.

If the Python extension still shows an old interpreter, run **Python: Select
Interpreter** and choose `.venv\Scripts\python.exe` for this project.

## Playing

Run `/arcade`, select a game, and choose another server member. Only that member can
accept or decline. Accepting replaces the challenge with a board in the same
message.

Challenges expire after two minutes. Games expire after five minutes without
an interaction. Finished and expired games disable their buttons and release
their event handlers. Games are held in memory and do not survive bot restarts;
start a new challenge after restarting.

## Layout

```text
discord-arcade-bot/
├── main.py              # Entry point and logging configuration
├── bot.py               # GameBot, extensions, command sync
├── config.py            # Environment loading and validation
├── games/
│   ├── __init__.py
│   ├── arcade.py        # Owns /arcade and registers game commands
│   ├── tictactoe.py     # Tic-tac-toe state and UI
|   ├── minesweeper.py   # Currently empty; implement when needed
|   ├── battleship.py    # Currently empty; implement when needed
│   ├── connect4.py      # Connect 4 state and UI
│   └── views.py         # Shared challenge and timeout handling
├── tests/
│   └── ...              # Unit tests for games, config, and registration
├── .env.example
├── .gitignore
└── requirements.txt
```

Add new game commands to the `Arcade` cog in `games/arcade.py`, keeping their
rules and views in their own game modules. If a game grows substantially,
split that module into a package with `logic.py` and `views.py`.

Logs go to the console and `discord.log`. The file rotates at approximately
5 MB with two backups; log files and local environment files are ignored by Git.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests run without a bot token or live Discord requests. They cover all 5,478
reachable tic-tac-toe boards, competing button clicks, finished games, timeouts,
failed message edits, configuration validation, and guild/global registration.
Connect 4 tests cover all 69 winning lines for both colors, gravity, full columns,
draws, player permissions, overlapping moves, and challenge/game cleanup.
