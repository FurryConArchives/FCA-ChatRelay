from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class DiscordConfig:
    token: str
    guild_id: int


@dataclass(frozen=True)
class TelegramConfig:
    token: str
    telegram_api_url: str


@dataclass(frozen=True)
class BridgeMapping:
    name: str
    discord_channel_ids: List[int]
    telegram_chat_ids: List[int]
    discord_webhooks: Dict[int, str]


@dataclass(frozen=True)
class AppConfig:
    discord: DiscordConfig
    telegram: TelegramConfig
    bridges: List[BridgeMapping]


def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    discord_raw = raw.get("discord", {})
    telegram_raw = raw.get("telegram", {})
    bridges_raw = raw.get("bridges", [])

    discord = DiscordConfig(
        token=str(discord_raw.get("token", "")),
        guild_id=int(discord_raw.get("guild_id", 0)),
    )
    telegram = TelegramConfig(
        token=str(telegram_raw.get("token", "")),
        telegram_api_url=str(telegram_raw.get("telegram_api_url", "")),
    )

    bridges: List[BridgeMapping] = []
    for item in bridges_raw:
        name = str(item.get("name", ""))
        discord_ids = [int(value) for value in item.get("discord_channel_ids", [])]
        telegram_ids = [int(value) for value in item.get("telegram_chat_ids", [])]
        raw_webhooks = item.get("discord_webhooks", {})
        discord_webhooks = {int(key): str(value) for key, value in raw_webhooks.items()}
        bridges.append(
            BridgeMapping(
                name=name,
                discord_channel_ids=discord_ids,
                telegram_chat_ids=telegram_ids,
                discord_webhooks=discord_webhooks
            )
        )

    return AppConfig(discord=discord, telegram=telegram, bridges=bridges)
