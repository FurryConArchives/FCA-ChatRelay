# Pure routing logic for relaying messages/events between platforms
from typing import Any, Dict, List, Set


class MessageRouter:
    def __init__(self, config, discord_client, media_handler, logger, telegram_client, msgmap_repo=None):
        self.config = config
        self.discord_client = discord_client
        self.media_handler = media_handler
        self.logger = logger
        self.telegram_client = telegram_client
        self.msgmap_repo = msgmap_repo

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
        blocked = [u.lower() for u in getattr(self.config.telegram, 'blocked_telegram_usernames', [])]
        self.logger.debug(f"Blocked usernames from config: {blocked}")
        username = username_map.get(from_id, '').lower()
        self.logger.debug(f"Checking username '{username}' (from_id={from_id}) against blocked list.")
        if username in blocked:
            return
        name = user_map.get(from_id, f"User_{from_id}") if from_id else "Unknown"
        avatar_url = None
        if from_id and from_id in username_map:
            # This API is pubic. Enjoy it, tg.tabs.gay doesn't easily support it.
            avatar_url = f"https://furryconarchives.org/api/telegram-avatar/{username_map[from_id]}"
        # Media handling
        file_payloads = await self.media_handler.telegram_to_discord(msg)
        content = f"{name}: {text}" if text else None
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
        except Exception as exc:
            self.logger.error(f"Failed to relay Telegram message {msg_id} to Discord: {exc}", exc_info=True)

    async def relay_fluxer_to_discord(self, message: Any):
        # message: Fluxer message object or dict
        author = getattr(message, 'author', None)
        display_name = getattr(author, 'display_name', None) if author else None
        username = getattr(author, 'username', None) if author else None
        text = getattr(message, 'content', None) or ''
        name = display_name or username or 'Unknown'
        avatar_url = getattr(author, 'avatar_url', None) if author else None
        file_payloads = await self.media_handler.fluxer_to_discord(message)
        content = f"{text}" if text else None
        prefixed = f"{content}" if content else None
        channel_id = getattr(message, 'channel_id', None)
        mapping = None
        if channel_id is not None:
            channel_id_str = str(channel_id)
            for bridge in getattr(self.config, 'bridges', []):
                fluxer_webhook = getattr(bridge, 'fluxer_webhook', None)
                discord_webhook = getattr(bridge, 'discord_webhook', None)
                if fluxer_webhook:
                    webhook_keys = [str(k) for k in fluxer_webhook.keys()]
                    if channel_id_str in webhook_keys and discord_webhook:
                        mapping = type('Mapping', (), {'discord_webhook': discord_webhook})()
                        break
        if not mapping:
            self.logger.warning(f"No mapping found for Fluxer channel {channel_id}, cannot relay to Discord.")
            return
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
        except Exception as exc:
            self.logger.error(f"Failed to relay Fluxer message to Discord: {exc}", exc_info=True)

    async def relay_fluxer_to_telegram(self, message: Any):
        # message: Fluxer message object or dict
        author = getattr(message, 'author', None)
        display_name = getattr(author, 'display_name', None) if author else None
        username = getattr(author, 'username', None) if author else None
        text = getattr(message, 'content', None) or ''
        name = display_name or username or 'Unknown'
        file_payloads = await self.media_handler.fluxer_to_telegram(message)
        content = f"{name}: {text}" if text else None
        channel_id = getattr(message, 'channel_id', None)
        mapping = None
        if channel_id is not None:
            channel_id_str = str(channel_id)
            for bridge in getattr(self.config, 'bridges', []):
                fluxer_webhook = getattr(bridge, 'fluxer_webhook', None)
                telegram_chat_id = getattr(bridge, 'telegram_chat_id', None)
                if fluxer_webhook:
                    webhook_keys = [str(k) for k in fluxer_webhook.keys()]
                    self.logger.debug(f"Checking channel_id {channel_id_str} against fluxer_webhook keys: {webhook_keys}")
                    if channel_id_str in webhook_keys:
                        mapping = type('Mapping', (), {'telegram_chat_id': telegram_chat_id})()
                        break
        if not mapping:
            self.logger.warning(f"No mapping found for Fluxer channel {channel_id}, cannot relay to Telegram.")
            return
        if not content and not file_payloads:
            return
        try:
            await self.telegram_client.send_message(
                mapping=mapping,
                content=content,
                file_payloads=file_payloads,
                author_name=name,
            )
        except Exception as exc:
            self.logger.error(f"Failed to relay Fluxer message to Telegram: {exc}", exc_info=True)


    async def relay_telegram_to_fluxer(self, mapping: Any, msg: dict, user_map: Dict[int, str], username_map: Dict[int, str], bot_user_ids: Set[int], chat_id: int):
        msg_id = msg.get("id")
        from_id = msg.get("from_id")
        text = msg.get("message", "")
        if msg.get("_") == "messageService":
            return
        if not text and not msg.get("media"):
            return
        if from_id and (from_id < 0 or from_id in bot_user_ids):
            return
        name = user_map.get(from_id, f"User_{from_id}") if from_id else "Unknown"
        # Media handling (if needed, implement media relay)
        try:
            await self.fluxer.send_message(
                mapping=mapping,
                content=text,
                author_name=name,
            )
        except Exception as exc:
            self.logger.error(f"Failed to relay Telegram message {msg_id} to Fluxer: {exc}", exc_info=True)

    async def relay_discord_to_fluxer(self, mapping: Any, message: Any):
        # message: discord.Message
        name = getattr(message.author, 'display_name', None) or getattr(message.author, 'name', 'Unknown')
        text = getattr(message, 'content', None) or ''
        if not text:
            return
        try:
            await self.fluxer.send_message(
                mapping=mapping,
                content=text,
                author_name=name,
            )
            self.logger.info(f"Relayed Discord message {getattr(message, 'id', '?')} to Fluxer")
        except Exception as exc:
            self.logger.error(f"Failed to relay Discord message to Fluxer: {exc}", exc_info=True)

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
