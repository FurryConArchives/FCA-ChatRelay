# FCA Telegram-Discord-Fluxer Bridge

Relay messages and media between Telegram, Fluxer, and Discord.

## Overview

This bridge relays messages and media between:
- **Telegram** groups/channels
- **Discord** channels (via bot and webhooks)
- **Fluxer** channels (via bot and webhooks)

It supports multiple Telegram groups and multiple Discord/Fluxer channels, but only within a single Discord/Fluxer guild (server). It does **not** support Discord forum channels, threads, or Telegram topics—only standard groups and channels.

---

## Requirements

- Python 3.10+
- All dependencies in `requirements.txt`

---

## Quick Start

1. **Clone the repository**
2. **Create a virtual environment**
	```sh
	python -m venv .venv
	source .venv/bin/activate  # or .venv\Scripts\activate on Windows
	```
3. **Install dependencies**
	```sh
	pip install -r requirements.txt
	```
4. **Copy and edit config**
	```sh
	cp config.json.example config.json
	# Edit config.json with your tokens, IDs, and settings
	```
5. **Run the bridge**
	```sh
	python main.py
	```

---

## Module Setup Guide

### Telegram

- Create a Telegram bot via [@BotFather](https://t.me/BotFather)
- Add the bot to your group/channel as an admin
- Get the bot token and add it to `config.json` under `telegram.token`
- Set `telegram_api_url` to your MadelineProto endpoint or use the default
- Optionally, set `blocked_telegram_usernames` to prevent relaying from certain users/bots

### Discord

- Create a Discord bot at [Discord Developer Portal](https://discord.com/developers/applications)
- Enable the **MESSAGE CONTENT** intent for your bot
- Invite the bot to your server with appropriate permissions (manage webhooks, read/send messages, etc.)
- Add the bot token to `config.json` under `discord.token`
- Add your guild/server ID to `discord.guild_id`
- For each channel you want to bridge, create a webhook or let the bot create one automatically

### Fluxer

- Create a Fluxer bot and obtain its token using the account settings inside the app.
- Add the token to `config.json` under `fluxer.token`
- Invite the bot to your server with appropriate permissions (manage webhooks, read/send messages, etc.)
- Add your guild/server ID to `fluxer.guild_id`
- For each channel you want to bridge, add the webhook URL to `fluxer_webhook` in your bridge mapping

---

## Configuration

Edit `config.json` to map Telegram chat IDs, Discord channel IDs/webhooks, and Fluxer channel IDs/webhooks. See `config.json.example` for a template.

---

## Features

- Relays text and media (photos, docs, audio, video)
- Supports group/channel mapping via `bridges` in config
- Discord webhooks for Telegram names/avatars
- Telegram information is proxied via MadelineProto API Server endpoint
- Blocklist for Telegram usernames

---

## Troubleshooting

- Ensure all tokens and IDs are correct in `config.json`
- The bridge will not start if only one service is enabled
- Check logs for errors and adjust permissions as needed

---

## License

MIT License
