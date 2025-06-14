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
   Users listed in `superadmins.txt` have extended permissions to manage the admin list.

4. Run the bot:

```bash
python bot.py
```

Use `/help` in the chat to see the list of available commands.

The bot stores events in a local SQLite database `events.db`.

When scheduling an event you will be asked for:

1. **Title** – short summary of the event
2. **Description** – longer text describing the event
3. **Date** and **Time**
4. **Location**
