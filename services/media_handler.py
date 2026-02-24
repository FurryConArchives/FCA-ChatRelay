# Handles all media download, size checks, and conversions
from typing import Any, List, Tuple

class MediaHandler:
    async def fluxer_to_discord(self, message: Any) -> List[Tuple[bytes, str]]:
        # TODO: Implement Fluxer media extraction and conversion
        return []
    
    async def fluxer_to_telegram(self, message: Any) -> List[Tuple[bytes, str]]:
        # TODO: Implement Fluxer media extraction and conversion
        return []

    async def discord_to_telegram(self, message: Any) -> List[Tuple[bytes, str]]:
        # TODO: Implement Discord media extraction and conversion
        return []
    
    async def discord_to_fluxer(self, message: Any) -> List[Tuple[bytes, str]]:
        # TODO: Implement Discord media extraction and conversion
        return []
    
    async def telegram_to_discord(self, message: Any) -> List[Tuple[bytes, str]]:
        # TODO: Implement Telegram media extraction and conversion
        return []

    async def telegram_to_fluxer(self, message: Any) -> List[Tuple[bytes, str]]:
        # TODO: Implement Telegram media extraction and conversion
        return []