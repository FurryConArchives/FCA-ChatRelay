# Core data models for bridge
from dataclasses import dataclass
from typing import Dict, List, Optional

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
    api_base: Optional[str] = None

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
