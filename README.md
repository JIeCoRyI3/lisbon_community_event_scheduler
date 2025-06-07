# Lisbon Community Event Scheduler Bot

This repository contains a simple Telegram bot that lets users schedule community events in Lisbon.

## Setup

1. Create a Python environment and install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project root with your bot token:

```
BOT_TOKEN=YOUR_TELEGRAM_TOKEN
```

3. Add Telegram usernames of admins to `admins.txt` (one per line). These users can delete events.

4. Run the bot:

```bash
python bot.py
```

Use `/help` in the chat to see the list of available commands.

The bot stores events in a local SQLite database `events.db`.
