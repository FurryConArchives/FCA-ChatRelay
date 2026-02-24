# Pure routing logic for relaying messages/events between platforms
from typing import Any, Dict, List, Set

class MessageRouter:
    def __init__(self, discord_client, media_handler, logger, telegram_client):
        self.discord_client = discord_client
        self.media_handler = media_handler
        self.logger = logger
        self.telegram_client = telegram_client

    async def relay_discord_to_telegram(self, mapping: Any, message: Any):
        # message: discord.Message
        name = getattr(message.author, 'display_name', None) or getattr(message.author, 'name', 'Unknown')
        text = getattr(message, 'content', None) or ''
        content = f"{name}: {text}" if text else None
        file_payloads = await self.media_handler.discord_to_telegram(message)
        if not content and not file_payloads:
            return
        try:
            await self.telegram_client.send_message(
                mapping=mapping,
                content=content,
                file_payloads=file_payloads,
                author_name=name,
            )
            self.logger.info(f"Relayed Discord message {getattr(message, 'id', '?')} to Telegram")
        except Exception as exc:
            self.logger.error(f"Failed to relay Discord message to Telegram: {exc}", exc_info=True)

    async def relay_telegram_to_discord(self, mapping: Any, msg: Dict, user_map: Dict[int, str], username_map: Dict[int, str], bot_user_ids: Set[int], chat_id: int):
        msg_id = msg.get("id")
        from_id = msg.get("from_id")
        text = msg.get("message", "")
        # Deduplication and filtering should be handled by poller/state
        if msg.get("_") == "messageService":
            return
        if not text and not msg.get("media"):
            return
        if from_id and (from_id < 0 or from_id in bot_user_ids):
            return
        if from_id and from_id in username_map:
            if username_map[from_id].lower() in getattr(mapping, 'blocked_telegram_usernames', []):
                return
        name = user_map.get(from_id, f"User_{from_id}") if from_id else "Unknown"
        avatar_url = None
        if from_id and from_id in username_map:
            # This API is pubic. Enjoy it, tg.tabs.gay doesn't easily support it.
            avatar_url = f"https://furryconarchives.org/api/telegram-avatar/{username_map[from_id]}"
        # Media handling
        file_payloads = await self.media_handler.telegram_to_discord(msg)
        content = text if text else None
        prefixed = f"{name}: {content}" if content else None
        if not prefixed and not file_payloads:
            return
        try:
            await self.discord_client.send_message(
                mapping=mapping,
                content=content,
                prefixed_content=prefixed,
                file_payloads=file_payloads,
                display_name=name,
                avatar_url=avatar_url,
            )
            self.logger.info(f"Relayed Telegram message {msg_id} to Discord")
        except Exception as exc:
            self.logger.error(f"Failed to relay Telegram message {msg_id} to Discord: {exc}", exc_info=True)

    async def relay_fluxer_to_discord(self, mapping: Any, message: Any):
        # message: Fluxer message object or dict
        author = getattr(message, 'author', None)
        username = getattr(author, 'username', None) if author else None
        text = getattr(message, 'content', None) or ''
        name = username or 'Unknown'
        avatar_url = getattr(author, 'avatar_url', None) if author else None
        file_payloads = await self.media_handler.fluxer_to_discord(message)
        content = text if text else None
        prefixed = f"{name}: {content}" if content else None
        if not prefixed and not file_payloads:
            return
        try:
            await self.discord_client.send_message(
                mapping=mapping,
                content=content,
                prefixed_content=prefixed,
                file_payloads=file_payloads,
                display_name=name,
                avatar_url=avatar_url,
            )
            self.logger.info(f"Relayed Fluxer message to Discord")
        except Exception as exc:
            self.logger.error(f"Failed to relay Fluxer message to Discord: {exc}", exc_info=True)

    async def relay_telegram_to_fluxer(self, mapping: Any, message: Any):
        # TODO: Implement relay logic to Fluxer
        pass

    async def relay_discord_to_fluxer(self, mapping: Any, message: Any):
        # TODO: Implement relay logic to Fluxer
        pass

    async def relay_join(self, mapping: Any, platform: str, user_name: str):
        join_msg = f"📌 {user_name} joined the {platform} Chat"
        try:
            await self.discord_client.send_message(
                mapping=mapping,
                content=join_msg,
                prefixed_content=join_msg,
                file_payloads=[],
                display_name="System",
                avatar_url=None,
            )
            await self.telegram_client.send_message(
                mapping=mapping,
                content=join_msg,
                file_payloads=[],
                author_name="System",
            )
            self.logger.info(f"Relayed join event for {user_name} from {platform}")
        except Exception as exc:
            self.logger.error(f"Failed to relay join event: {exc}", exc_info=True)

    async def relay_leave(self, mapping: Any, platform: str, user_name: str):
        leave_msg = f"📍 {user_name} left the {platform} Chat"
        try:
            await self.discord_client.send_message(
                mapping=mapping,
                content=leave_msg,
                prefixed_content=leave_msg,
                file_payloads=[],
                display_name="System",
                avatar_url=None,
            )
            await self.telegram_client.send_message(
                mapping=mapping,
                content=leave_msg,
                file_payloads=[],
                author_name="System",
            )
            self.logger.info(f"Relayed leave event for {user_name} from {platform}")
        except Exception as exc:
            self.logger.error(f"Failed to relay leave event: {exc}", exc_info=True)

    async def relay_donation_alert(self, donor_name, amount, message):
        # TODO: Implement donation alert relay logic
        pass
