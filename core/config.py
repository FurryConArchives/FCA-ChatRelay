from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

@dataclass(frozen=True)
class DiscordConfig:
    enabled: bool
    token: str
    guild_id: int

@dataclass(frozen=True)
class FluxerConfig:
    enabled: bool
    token: str
    guild_id: int

@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool
    token: str
    blocked_telegram_usernames: List[str]
    telegram_api_url: str

@dataclass(frozen=True)
class BridgeMapping:
    enabled: bool
    name: str
    discord_webhook: Dict[int, str]
    fluxer_webhook: Dict[int, str]
    telegram_chat_id: List[int]

@dataclass(frozen=True)
class AppConfig:
    discord: DiscordConfig
    telegram: TelegramConfig
    bridges: List[BridgeMapping]
    fluxer: FluxerConfig

def load_config(path: str) -> AppConfig:
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    discord_raw = raw.get("discord", {})
    telegram_raw = raw.get("telegram", {})
    fluxer_raw = raw.get("fluxer", {})
    bridges_raw = raw.get("bridges", [])

    discord = DiscordConfig(
        enabled=bool(discord_raw.get("enabled", True)),
        token=str(discord_raw.get("token", "")),
        guild_id=int(discord_raw.get("guild_id", 0)),
    )

    fluxer = FluxerConfig(
        enabled=bool(fluxer_raw.get("enabled", True)),
        token=str(fluxer_raw.get("token", "")),
        guild_id=int(fluxer_raw.get("guild_id", 0)),
    )

    telegram = TelegramConfig(
        enabled=bool(telegram_raw.get("enabled", True)),
        token=str(telegram_raw.get("token", "")),
        blocked_telegram_usernames=telegram_raw.get("blocked_telegram_usernames", []),
        telegram_api_url=str(telegram_raw.get("telegram_api_url", "")),
    )

    bridges: List[BridgeMapping] = []
    for item in bridges_raw:
        if not item.get("enabled", True):
            continue
        name = str(item.get("name", ""))
        telegram_ids = [int(value) for value in item.get("telegram_chat_id", [])]
        raw_discord_webhooks = item.get("discord_webhook", {})
        discord_webhook = {int(key): str(value) for key, value in raw_discord_webhooks.items()}
        raw_fluxer_webhooks = item.get("fluxer_webhook", {})
        fluxer_webhook = {int(key): str(value) for key, value in raw_fluxer_webhooks.items()}
        bridges.append(
            BridgeMapping(
                enabled=bool(item.get("enabled", True)),
                name=name,
                discord_webhook=discord_webhook,
                fluxer_webhook=fluxer_webhook,
                telegram_chat_id=telegram_ids
            )
        )

    return AppConfig(discord=discord, telegram=telegram, bridges=bridges, fluxer=fluxer)
