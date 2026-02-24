# FCA Telegram-Discord Bridge


Relay messages and media between Telegram and Discord.

**Note:** This bridge supports relaying between multiple Telegram groups and multiple Discord channels, but only within a single Discord guild (server). It does not support Discord forum channels, threads, or Telegram topics—only standard groups and channels.

## Quick Setup

1. Create a virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `config.json.example` to `config.json` and add your tokens and IDs
4. Start: `python main.py`

## Features

- Relays text and media (photos, docs, audio, video)
- Supports group mapping via `bridges` in config
- Discord webhooks for Telegram names/avatars
- Discord bot needs MESSAGE CONTENT intent enabled
