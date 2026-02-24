# Fluxer transport client
from typing import Any, Optional


import fluxer


class FluxerClient:
    def __init__(self, bot, logger, router=None):
        self.bot = bot
        self.logger = logger
        self.router = router
        self._on_message_callback = None

        @self.bot.event
        async def on_message(message):
            self.logger.info(f"{getattr(getattr(message, 'author', None), 'username', None)}: {getattr(message, 'content', None)}")
            if self.router:
                await self.router.relay_fluxer_to_discord(message)
                await self.router.relay_fluxer_to_telegram(message)
            elif self._on_message_callback:
                await self._on_message_callback(message)

    def set_on_message(self, callback):
        self._on_message_callback = callback

    async def start(self, token):
        self.logger.info("Starting Fluxer bot")
        await self.bot.start(token)
     
    async def send_webhook(self, mapping: Any, content: Optional[str], file_payloads: Optional[list] = None, username: Optional[str] = None, avatar_url: Optional[str] = None):
        """Relay a message to a Fluxer webhook endpoint."""
        import aiohttp
        if not mapping or not hasattr(mapping, 'fluxer_webhook'):
            self.logger.warning("No fluxer_webhook mapping provided.")
            return
        for channel_id, webhook_url in getattr(mapping, 'fluxer_webhook', {}).items():
            if not webhook_url:
                continue
            form = aiohttp.FormData()
            payload = {
                "username": username or "Relay",
                "avatar_url": avatar_url,
                "content": content or "",
                "attachments": [],
            }
            if file_payloads:
                for i, (data, filename) in enumerate(file_payloads):
                    payload["attachments"].append({"id": i, "filename": filename})
                    form.add_field(f"files[{i}]", data, filename=filename, content_type="application/octet-stream")
            form.add_field("payload_json", __import__('json').dumps(payload), content_type="application/json")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(webhook_url, data=form) as resp:
                        if resp.status in (200, 201):
                            self.logger.info(f"Sent message to Fluxer via webhook for channel {channel_id}")
                        else:
                            text = await resp.text()
                            self.logger.error(f"Fluxer webhook failed for channel {channel_id}: {resp.status} {text}")
            except Exception as exc:
                self.logger.error(f"Exception sending to Fluxer webhook for channel {channel_id}: {exc}", exc_info=True)

    async def send_message(self, channel_id: int, content: str, **kwargs):
            """Send a plain text message to a Fluxer channel using the bot (not webhook)."""
            try:
                channel = await self.bot.fetch_channel(channel_id)
                await channel.send(content)
            except Exception as exc:
                self.logger.error(f"Failed to send message to Fluxer channel {channel_id}: {exc}", exc_info=True)
