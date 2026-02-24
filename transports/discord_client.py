# Discord transport client
from typing import Any, Optional, Sequence, Tuple
import discord

class DiscordClient:
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger

        @self.bot.event
        async def on_message(message):
            # Ignore messages sent by webhooks to prevent relay loops
            if getattr(message, 'webhook_id', None) is not None:
                self.logger.debug(f"Ignoring webhook message (id={getattr(message, 'id', '?')}) to prevent relay loop.")
                return
            name = getattr(message.author, 'display_name', None) or getattr(message.author, 'name', 'Unknown')
            text = getattr(message, 'content', None) or ''
            self.logger.info(f"{name}: {text}")

    async def start(self, token):
        self.logger.info("Starting Discord bot")
        await self.bot.start(token)
        
    async def send_message(self, mapping: Any, content: Optional[str], prefixed_content: Optional[str], file_payloads: Sequence[Tuple[bytes, str]], display_name: str, avatar_url: Optional[str]):
        # mapping.discord_webhook: Dict[int, str]
        import aiohttp
        files = [discord.File(fp=bytes_data, filename=filename) for bytes_data, filename in file_payloads] if file_payloads else []
        for channel_id, webhook_url in mapping.discord_webhook.items():
            try:
                if webhook_url:
                    async with aiohttp.ClientSession() as session:
                        webhook = discord.Webhook.from_url(webhook_url, session=session)
                        await webhook.send(
                            content,
                            username=display_name,
                            avatar_url=avatar_url,
                            files=files if files else None,
                        )
                    continue
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    channel = await self.bot.fetch_channel(channel_id)
                if prefixed_content is None and not files:
                    self.logger.warning(f"No content and no files for channel {channel_id}, skipping")
                    continue
                await channel.send(prefixed_content, files=files)
                self.logger.info(f"Successfully sent message to Discord channel {channel_id}")
            except Exception as exc:
                self.logger.error(f"Failed to send message to Discord channel {channel_id}: {exc}", exc_info=True)

    async def send_webhook(self, webhook_url: str, content: Optional[str] = None, username: Optional[str] = None, avatar_url: Optional[str] = None, files: Optional[Sequence[Tuple[bytes, str]]] = None, session=None):
        """Send a message via Discord webhook, using aiohttp session if provided."""
        import discord
        import aiohttp
        close_session = False
        if session is None:
            session = aiohttp.ClientSession()
            close_session = True
        try:
            file_objs = [discord.File(fp=bytes_data, filename=filename) for bytes_data, filename in files] if files else None
            webhook = discord.Webhook.from_url(webhook_url, session=session)
            await webhook.send(
                content,
                username=username,
                avatar_url=avatar_url,
                files=file_objs
            )
            self.logger.info(f"Sent message via webhook {webhook_url}")
        except Exception as exc:
            self.logger.error(f"Failed to send webhook message: {exc}", exc_info=True)
            raise
        finally:
            if close_session:
                await session.close()
