from __future__ import annotations

import asyncio
import io
import logging
import sqlite3
import aiohttp
import discord

from typing import Awaitable, Callable, Iterable, Optional, Sequence, Tuple
from discord.ext import commands
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

from .config import AppConfig, BridgeMapping, load_config


class BridgeApp:
    async def _poll_latest_donation(self) -> None:
        """
        Periodically scan the latest donation API and alert both Discord and Telegram if a new donation is detected.
        """
        last_donation_id = None
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://furryconarchives.org/api/latest-donation"
                    async with session.get(url, timeout=10) as response:
                        if response.status != 200:
                            self.logger.warning("Failed to fetch latest donation: %s", response.status)
                            await asyncio.sleep(60)
                            continue
                        data = await response.json()
                        donation = data.get("latest_donation", {})
                        name = donation.get("name", "Anonymous")
                        amount = donation.get("amount", "0.00")
                        discord_username = donation.get("discord_username", "")

                        donation_id = f"{name}-{amount}-{discord_username}"
                        if donation_id == last_donation_id:
                            await asyncio.sleep(60)
                            continue
                        last_donation_id = donation_id

                        # Strip #0000 if present
                        if discord_username:
                            discord_username = discord_username.split('#')[0]
                        message = f"{discord_username} donated ${amount}"
                        await self.alert_kofi_donation(name, float(amount), message)
                        self.logger.info(f"Donation alert sent: {message}")
            except Exception as exc:
                self.logger.error(f"Error polling latest donation: {exc}", exc_info=True)
            await asyncio.sleep(60)
    def __init__(self, config_path: str) -> None:
        self.config: AppConfig = load_config(config_path)
        self.logger = logging.getLogger("BridgeApp")
        self.discord_bot: Optional[commands.Bot] = None
        self.telegram_app = None
        self.discord_ready = asyncio.Event()
        self.processed_message_ids: dict[int, set[int]] = {}
        self.blocked_telegram_usernames = {"fcarelay_bot", "countersignbot"}

        self.db_path = "bridge_state.db"
        self._init_database()
        self._load_processed_message_ids()

    async def alert_kofi_donation(self, donor_name: str, amount: float, message: str = "") -> None:
        """
        Alert both Discord and Telegram chats about a Ko-fi donation.
        Args:
            donor_name: Name of the donor.
            amount: Donation amount.
            message: Optional message from the donor.
        """
        alert_text = f"☕ Donation received!\nDonor: {donor_name}\nAmount: ${amount:.2f}"
        if message:
            alert_text += f"\nMessage: {message}"

        for mapping in self.config.bridges:
            await self._send_to_discord_channels(
                mapping,
                alert_text,
                alert_text,
                [],
                "Donation Alert",
                None,
            )
            await self._send_to_telegram_text(mapping, alert_text)


    def _init_database(self) -> None:
        """Initialize SQLite database for tracking processed message IDs."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    PRIMARY KEY (chat_id, message_id)
                )
            """)
            conn.commit()
            conn.close()
            self.logger.info("Database initialized: %s", self.db_path)
        except Exception as exc:
            self.logger.warning("Failed to initialize database: %s", exc)
    def _load_processed_message_ids(self) -> None:
        """Load processed message IDs from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id, message_id FROM processed_messages")
            rows = cursor.fetchall()
            for chat_id, msg_id in rows:
                if chat_id not in self.processed_message_ids:
                    self.processed_message_ids[chat_id] = set()
                self.processed_message_ids[chat_id].add(msg_id)
            conn.close()
            total = sum(len(ids) for ids in self.processed_message_ids.values())
            self.logger.info(f"Loaded {total} processed message IDs across {len(self.processed_message_ids)} chats")
        except Exception as exc:
            self.logger.warning("Failed to load message IDs from database: %s", exc)
    def _save_last_message_id(self, chat_id: int, message_id: int) -> None:
        """Save processed message ID to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO processed_messages (chat_id, message_id) VALUES (?, ?)",
                (chat_id, message_id)
            )
            conn.commit()
            conn.close()
            self.logger.debug(f"Saved msg_id={message_id} for chat_id={chat_id}")
        except Exception as exc:
            self.logger.warning("Failed to save message ID to database: %s", exc)
    def _find_by_discord(self, channel_id: int) -> Optional[BridgeMapping]:
        for mapping in self.config.bridges:
            if channel_id in mapping.discord_channel_ids:
                return mapping
        return None
    def _find_by_telegram(self, chat_id: int) -> Optional[BridgeMapping]:
        for mapping in self.config.bridges:
            if chat_id in mapping.telegram_chat_ids:
                return mapping
        return None
    async def _retry(self, action: Callable[[], Awaitable[None]], label: str) -> bool:
        retries = 2
        for attempt in range(retries + 1):
            try:
                await action()
                return True
            except Exception as exc:
                if attempt >= retries:
                    self.logger.warning("%s failed: %s", label, exc)
                else:
                    await asyncio.sleep(1 + attempt)
        return False
    async def _discord_attachments_to_payloads(
        self, attachments: Iterable[discord.Attachment]
    ) -> list[Tuple[bytes, str]]:
        payloads: list[Tuple[bytes, str]] = []
        for attachment in attachments:
            try:
                data = await attachment.read()
            except Exception as exc:
                self.logger.warning("Failed to read Discord attachment: %s", exc)
                continue
            filename = attachment.filename or "discord_attachment"
            payloads.append((data, filename))
        return payloads
    def _append_urls_to_content(self, content: Optional[str], urls: Sequence[str]) -> Optional[str]:
        if not urls:
            return content
        base = content or ""
        if base:
            return f"{base}\n" + "\n".join(urls)
        return "\n".join(urls)
    async def _fetch_telegram_avatar_url(self, user_id: Optional[int]) -> Optional[str]:
        if not user_id:
            return None
        try:
            photos = await self.telegram_app.bot.get_user_profile_photos(user_id, limit=1)
            if photos.photos:
                file = await photos.photos[0][-1].get_file()
                return file.file_path
        except Exception:
            self.logger.debug("Failed to fetch Telegram avatar for user %s", user_id)
        return None
    async def _fetch_endpoint_messages(self, chat_id: int, limit: int = 100) -> tuple[list[dict], dict[int, str], dict[int, str], set[int]]:
        """Fetch messages from the archival endpoint. Returns (messages, user_name_map, user_username_map, bot_user_ids)."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://{self.config.telegram.telegram_api_url}/api/messages.getHistory"
                params = {"limit": limit, "page": 1, "peer": chat_id}
                self.logger.debug(f"Fetching endpoint for chat_id={chat_id}, params={params}")
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        self.logger.warning("Endpoint fetch failed for chat %s: %s", chat_id, response.status)
                        return [], {}, {}, set()
                    data = await response.json()
                    user_map: dict[int, str] = {}
                    username_map: dict[int, str] = {}
                    bot_user_ids: set[int] = set()
                    users_list = data.get("response", {}).get("users", [])
                    for user in users_list:
                        user_id = user.get("id")
                        first = user.get("first_name", "")
                        last = user.get("last_name", "")
                        username = user.get("username", "")
                        is_bot = user.get("is_bot", False)
                        if first and last:
                            name = f"{first} {last}"
                        elif first:
                            name = first
                        elif username:
                            name = username
                        else:
                            name = f"User_{user_id}"
                        if user_id:
                            user_map[user_id] = name
                            if username:
                                username_map[user_id] = username
                            if is_bot:
                                bot_user_ids.add(user_id)
                    response_obj = data.get("response", {})
                    messages = response_obj.get("messages", [])
                    if messages:
                        msg_ids = [m.get("id") for m in messages if m.get("id")]
                        if msg_ids:
                            self.logger.info(f"Fetched {len(messages)} messages for chat_id={chat_id}, ID range: {min(msg_ids)}-{max(msg_ids)}")
                        else:
                            self.logger.info(f"Fetched {len(messages)} messages but no IDs found")
                    else:
                        self.logger.info(f"Fetched 0 messages from endpoint for chat_id={chat_id}")
                    return messages, user_map, username_map, bot_user_ids
        except asyncio.TimeoutError:
            self.logger.error(f"Endpoint fetch timeout for chat {chat_id}")
            return [], {}, {}, set()
        except Exception as exc:
            self.logger.error(f"Failed to fetch from endpoint for chat {chat_id}: {exc}", exc_info=True)
            return [], {}, {}, set()

    async def _process_endpoint_message(self, mapping: BridgeMapping, msg: dict, user_map: dict[int, str], username_map: dict[int, str], bot_user_ids: set[int], chat_id: int) -> None:
        """Process a single message from the endpoint response with secure media handling."""
        try:
            msg_id = msg.get("id")
            from_id = msg.get("from_id")
            text = msg.get("message", "")
    
            # 1. Deduplication and Basic Filtering
            if chat_id not in self.processed_message_ids:
                self.processed_message_ids[chat_id] = set()
            if msg_id and msg_id in self.processed_message_ids[chat_id]:
                return
            
            if msg.get("_") == "messageService":
                return
                
            if not text and not msg.get("media"):
                return
    
            if from_id and (from_id < 0 or from_id in bot_user_ids):
                return
    
            if from_id and from_id in username_map:
                if username_map[from_id].lower() in self.blocked_telegram_usernames:
                    return
    
            # Mark as processed
            if msg_id:
                self.processed_message_ids[chat_id].add(msg_id)
                self._save_last_message_id(chat_id, msg_id)
    
            # 2. Identity and Metadata
            name = user_map.get(from_id, f"User_{from_id}") if from_id else "Unknown"
            avatar_url = None
            if from_id and from_id in username_map:
                avatar_url = f"https://furryconarchives.org/api/telegram-avatar/{username_map[from_id]}"
    
            # 3. Secure Media Handling
            media = msg.get("media")
            cdn_links = []
            file_payloads = []
            filename = None

            if media:
                media_type = media.get("_")
                file_id = None
                # Extract file_id based on type
                if media_type == "messageMediaDocument":
                    doc = media.get("document", {})
                    file_id = doc.get("id") or doc.get("file_id")
                    for attr in doc.get("attributes", []):
                        if attr.get("_") == "documentAttributeFilename":
                            filename = attr.get("file_name")
                            break
                elif media_type == "messageMediaPhoto":
                    photo = media.get("photo", {})
                    file_id = photo.get("id") or photo.get("file_id")
                    filename = "telegram_photo.jpg"
                elif media_type == "messageMediaVideo":
                    video = media.get("video", {})
                    file_id = video.get("id") or video.get("file_id")
                    filename = "telegram_video.mp4"
                elif media_type == "messageMediaAudio":
                    audio = media.get("audio", {})
                    file_id = audio.get("id") or audio.get("file_id")
                    filename = "telegram_audio.mp3"
                elif media_type == "messageMediaVoice":
                    voice = media.get("voice", {})
                    file_id = voice.get("id") or voice.get("file_id")
                    filename = "telegram_voice.ogg"

                # Always use MadelineProto endpoint for ALL files
                peer_id = chat_id
                msg_id = msg.get('id')
                madeline_link = f"https://{self.config.telegram.telegram_api_url}/api/getMedia?peer={peer_id}&id={msg_id}"
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(madeline_link, timeout=30) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                if len(data) <= 10 * 1024 * 1024:
                                    file_payloads.append((data, filename or "telegram_file"))
                                    self.logger.info(f"Downloaded and buffered {filename} from MadelineProto for Discord.")
                                else:
                                    self.logger.info(f"File too large from MadelineProto ({len(data)} bytes). Posting link only.")
                                    # Format as Markdown hyperlink with file name
                                    cdn_links.append(f"[{filename or 'Telegram File'}]({madeline_link})")
                            else:
                                self.logger.error(f"MadelineProto download failed with status {resp.status}")
                                cdn_links.append(f"[Telegram File: {filename or 'media'}] Download: {madeline_link}")
                except Exception as exc:
                    self.logger.error(f"Failed to fetch Telegram media from MadelineProto: {exc}")
                    cdn_links.append(f"[Telegram File: {filename or 'media'}] Download: {madeline_link}")
    
            # 5. Build Final Text Payload
            # We never add the raw TG URL to full_text anymore.
            full_text = text if text else ""
            if cdn_links:
                # Append size warnings but NO token links
                full_text = self._append_urls_to_content(full_text, cdn_links)
                
            prefixed = f"{name}: {full_text}" if full_text else None
    
            if not prefixed and not file_payloads:
                return
    
            # 6. Relay to Discord
            try:
                if not self.discord_ready.is_set():
                    await asyncio.wait_for(self.discord_ready.wait(), timeout=5)
                await self._send_to_discord_channels(
                    mapping,
                    full_text,
                    prefixed,
                    file_payloads,
                    name,
                    avatar_url,
                )
            except Exception as discord_exc:
                self.logger.error(f"Discord relay failed: {discord_exc}", exc_info=True)
    
        except Exception as exc:
            self.logger.error(f"Failed to process endpoint message: {exc}", exc_info=True)

    async def _poll_endpoint_periodically(self) -> None:
        """Periodically fetch messages from the endpoint."""
        await asyncio.sleep(2)  # Wait for Discord to be ready
        self.logger.info("Starting endpoint polling task")
        poll_count = 0
        while True:
            try:
                poll_count += 1
                for mapping in self.config.bridges:
                    try:
                        for chat_id in mapping.telegram_chat_ids:
                            try:
                                messages, user_map, username_map, bot_user_ids = await self._fetch_endpoint_messages(chat_id, limit=15)
                                self.logger.debug(f"[Poll #{poll_count}] Fetched {len(messages)} messages for chat_id={chat_id}")
                                # Process in reverse chronological order (oldest first)
                                for msg in reversed(messages):
                                    try:
                                        msg_id = msg.get("id")
                                        await self._process_endpoint_message(mapping, msg, user_map, username_map, bot_user_ids, chat_id)
                                    except Exception as msg_exc:
                                        self.logger.error(f"Error processing message {msg.get('id')}: {msg_exc}", exc_info=True)
                                        continue
                            except Exception as chat_exc:
                                self.logger.error(f"Error fetching messages for chat_id={chat_id}: {chat_exc}", exc_info=True)
                                continue
                    except Exception as mapping_exc:
                        self.logger.error(f"Error processing mapping: {mapping_exc}", exc_info=True)
                        continue
                    
                self.logger.debug(f"[Poll #{poll_count}] Completed, sleeping 5 seconds")
                await asyncio.sleep(5)  # Fetch every 5 seconds for near-realtime
            except asyncio.CancelledError:
                self.logger.info("Polling task cancelled")
                raise
            except Exception as exc:
                self.logger.error(f"Unexpected error in polling loop: {exc}", exc_info=True)
                await asyncio.sleep(10)  # Back off on error
    def _build_discord_files(self, file_payloads: Sequence[Tuple[bytes, str]]) -> list[discord.File]:
        files: list[discord.File] = []
        for data, filename in file_payloads:
            files.append(discord.File(io.BytesIO(data), filename=filename))
        return files
    async def _send_to_discord_channels(
        self,
        mapping: BridgeMapping,
        content: Optional[str],
        prefixed_content: Optional[str],
        file_payloads: Sequence[Tuple[bytes, str]],
        display_name: str,
        avatar_url: Optional[str],
    ) -> None:
        if not self.discord_bot:
            self.logger.error("Discord bot not initialized")
            return
        self.logger.debug(f"_send_to_discord_channels called with {len(mapping.discord_channel_ids)} channels")
        for channel_id in mapping.discord_channel_ids:
            self.logger.debug(f"Attempting to send to Discord channel {channel_id}")
            files = self._build_discord_files(file_payloads)
            webhook_url = mapping.discord_webhooks.get(channel_id)
            if webhook_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        webhook = discord.Webhook.from_url(webhook_url, session=session)
                        await webhook.send(
                            content,
                            username=display_name,
                            avatar_url=avatar_url,
                            files=files,
                        )
                    self.logger.info(f"Sent to Discord via webhook for channel {channel_id}")
                    continue
                except Exception as exc:
                    self.logger.warning(
                        "Discord webhook send failed for %s: %s; falling back to bot send",
                        channel_id,
                        exc,
                    )
            channel = self.discord_bot.get_channel(channel_id)
            if channel is None:
                self.logger.info(f"Channel {channel_id} not found in cache, fetching...")
                try:
                    channel = await self.discord_bot.fetch_channel(channel_id)
                    self.logger.info(f"Successfully fetched channel {channel_id}")
                except Exception as exc:
                    self.logger.error(f"Discord channel not found: {channel_id}: {exc}")
                    continue
            if prefixed_content is None and not files:
                self.logger.warning(f"No content and no files for channel {channel_id}, skipping")
                continue
            
            self.logger.info(f"Sending to Discord channel {channel_id}: {prefixed_content[:60] if prefixed_content else 'files only'}")
            try:
                await channel.send(prefixed_content, files=files)
                self.logger.info(f"Successfully sent message to Discord channel {channel_id}")
            except Exception as exc:
                self.logger.error(f"Failed to send message to Discord channel {channel_id}: {exc}", exc_info=True)
    async def _send_to_telegram_chats(
        self, mapping: BridgeMapping, content: Optional[str], attachments: Iterable[discord.Attachment]
    ) -> None:
        for chat_id in mapping.telegram_chat_ids:
            if content:
                await self.telegram_app.bot.send_message(chat_id=chat_id, text=content)
            for attachment in attachments:
                if attachment.content_type and attachment.content_type.startswith("image/"):
                    await self.telegram_app.bot.send_photo(chat_id=chat_id, photo=attachment.url)
                else:
                    await self.telegram_app.bot.send_document(chat_id=chat_id, document=attachment.url)
    async def _send_to_telegram_text(self, mapping: BridgeMapping, content: Optional[str]) -> None:
        if not content:
            return
        for chat_id in mapping.telegram_chat_ids:
            try:
                await self.telegram_app.bot.send_message(chat_id=chat_id, text=content)
                self.logger.debug(f"Sent text to Telegram chat {chat_id}")
            except Exception as exc:
                self.logger.error(f"Failed to send text to Telegram chat {chat_id}: {exc}", exc_info=True)
    async def _send_to_telegram_files(
        self,
        mapping: BridgeMapping,
        content: Optional[str],
        file_payloads: Sequence[Tuple[bytes, str, Optional[str]]],
    ) -> None:
        for chat_id in mapping.telegram_chat_ids:
            try:
                if content:
                    await self.telegram_app.bot.send_message(chat_id=chat_id, text=content)
                for data, filename, content_type in file_payloads:
                    buffer = io.BytesIO(data)
                    buffer.name = filename
                    if content_type and content_type.startswith("image/"):
                        await self.telegram_app.bot.send_photo(chat_id=chat_id, photo=buffer)
                    else:
                        await self.telegram_app.bot.send_document(chat_id=chat_id, document=buffer)
                if content or file_payloads:
                    self.logger.debug(f"Sent files to Telegram chat {chat_id}")
            except Exception as exc:
                self.logger.error(f"Failed to send files to Telegram chat {chat_id}: {exc}", exc_info=True)
    async def _handle_telegram(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if not update.effective_chat or not message:
            return
        chat_id = update.effective_chat.id
        msg_id = message.message_id
        if chat_id not in self.processed_message_ids:
            self.processed_message_ids[chat_id] = set()
        if msg_id and msg_id in self.processed_message_ids[chat_id]:
            return
        if update.effective_user and update.effective_user.is_bot:
            return
        if update.effective_user and update.effective_user.username:
            username = update.effective_user.username.lower()
            if username in self.blocked_telegram_usernames:
                self.logger.info("Skipping blocked Telegram bot: %s", username)
                return
        if msg_id:
            self.processed_message_ids[chat_id].add(msg_id)
            self._save_last_message_id(chat_id, msg_id)
        chat_type = getattr(update.effective_chat, "type", None)
        self.logger.info(
            "Telegram message from chat_id=%s type=%s",
            chat_id,
            chat_type,
        )
        mapping = self._find_by_telegram(chat_id)
        if not mapping:
            return
        user = update.effective_user
        name = user.full_name if user else "Unknown"
        user_id = user.id if user else None
        text = message.text or message.caption or ""
        content = text if text else None
        prefixed_content = f"{name}: {text}" if text else None
        # Handle join/leave events
        if message.new_chat_members:
            for member in message.new_chat_members:
                join_msg = f"📌 {member.full_name or 'Unknown'} joined the Telegram Chat"
                await self._send_to_discord_channels(mapping, join_msg, join_msg, [], "System", None)
            return
        if message.left_chat_member:
            member = message.left_chat_member
            leave_msg = f"📍 {member.full_name or 'Unknown'} left the Telegram Chat"
            await self._send_to_discord_channels(mapping, leave_msg, leave_msg, [], "System", None)
            return
        file_payloads: list[Tuple[bytes, str]] = []
        bot_token = self.config.telegram.token
        # Helper to send oversized media notice with link
        async def send_oversized_notice(media_type, filename, file_path):
            # Use MadelineProto endpoint for oversized files
            madeline_link = f"https://{self.config.telegram.telegram_api_url}/api/getMedia?peer={chat_id}&id={msg_id}"
            notice = f"[Telegram] {media_type} '{filename}' too large to upload (>10MB). View original: {madeline_link}"
            await self._send_to_discord_channels(
                mapping,
                notice,
                notice,
                [],
                name,
                avatar_url,
            )
        # Photo
        if message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            data = await file.download_as_bytearray()
            file_path = getattr(file, 'file_path', None)
            if len(data) <= 10 * 1024 * 1024:
                file_payloads.append((bytes(data), "telegram_photo.jpg"))
            else:
                self.logger.warning(f"Telegram photo too large for Discord: {len(data)} bytes")
                await send_oversized_notice("Photo", "telegram_photo.jpg", file_path)
        # Document
        if message.document:
            file = await message.document.get_file()
            data = await file.download_as_bytearray()
            filename = message.document.file_name or "telegram_document"
            file_path = getattr(file, 'file_path', None)
            if len(data) <= 10 * 1024 * 1024:
                file_payloads.append((bytes(data), filename))
            else:
                self.logger.warning(f"Telegram document '{filename}' too large for Discord: {len(data)} bytes")
                await send_oversized_notice("Document", filename, file_path)
        # Video
        if message.video:
            file = await message.video.get_file()
            data = await file.download_as_bytearray()
            file_path = getattr(file, 'file_path', None)
            if len(data) <= 10 * 1024 * 1024:
                file_payloads.append((bytes(data), "telegram_video.mp4"))
            else:
                self.logger.warning(f"Telegram video too large for Discord: {len(data)} bytes")
                await send_oversized_notice("Video", "telegram_video.mp4", file_path)
        # Audio
        if message.audio:
            file = await message.audio.get_file()
            data = await file.download_as_bytearray()
            filename = message.audio.file_name or "telegram_audio.mp3"
            file_path = getattr(file, 'file_path', None)
            if len(data) <= 10 * 1024 * 1024:
                file_payloads.append((bytes(data), filename))
            else:
                self.logger.warning(f"Telegram audio '{filename}' too large for Discord: {len(data)} bytes")
                await send_oversized_notice("Audio", filename, file_path)
        # Voice
        if message.voice:
            file = await message.voice.get_file()
            data = await file.download_as_bytearray()
            file_path = getattr(file, 'file_path', None)
            if len(data) <= 10 * 1024 * 1024:
                file_payloads.append((bytes(data), "telegram_voice.ogg"))
            else:
                self.logger.warning(f"Telegram voice too large for Discord: {len(data)} bytes")
                await send_oversized_notice("Voice", "telegram_voice.ogg", file_path)
        if not content and not file_payloads:
            return
        avatar_url = await self._fetch_telegram_avatar_url(user_id)
        await self._send_to_discord_channels(
            mapping,
            content,
            prefixed_content,
            file_payloads,
            name,
            avatar_url,
        )
    async def start(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        self.discord_bot = commands.Bot(command_prefix="!", intents=intents)
        @self.discord_bot.event
        async def on_ready() -> None:
            self.logger.info("Discord connected as %s", self.discord_bot.user)
            self.discord_ready.set()

        @self.discord_bot.event
        async def on_message(message: discord.Message) -> None:
            self.logger.debug(f"Discord message from {message.author}: {message.content[:50] if message.content else '(no content)'}")
            if message.author.bot:
                self.logger.debug(f"Skipping bot message from {message.author}")
                return
            mapping = self._find_by_discord(message.channel.id)
            if not mapping:
                self.logger.debug(f"No mapping found for channel {message.channel.id}")
                return
            name = message.author.display_name
            text = message.content or ""
            content = f"{name}: {text}" if text else None
            if not content and not message.attachments:
                self.logger.debug("No content or attachments, skipping")
                return
            self.logger.info(f"Relaying Discord message: {content[:60] if content else 'attachments only'}")
            await self._send_to_telegram_chats(mapping, content, message.attachments)
            await self.discord_bot.process_commands(message)

        @self.discord_bot.event
        async def on_member_join(member: discord.Member) -> None:
            # Relay Discord member join to Telegram
            self.logger.info(f"Discord member joined: {member.display_name}")
            # Find all mappings that include this guild
            for mapping in self.config.bridges:
                if member.guild and member.guild.id in mapping.discord_guild_ids:
                    join_msg = f"📌 {member.display_name or 'Unknown'} joined the Discord Chat"
                    await self._send_to_telegram_text(mapping, join_msg)

        @self.discord_bot.event
        async def on_member_remove(member: discord.Member) -> None:
            # Relay Discord member leave to Telegram
            self.logger.info(f"Discord member left: {member.display_name}")
            for mapping in self.config.bridges:
                if member.guild and member.guild.id in mapping.discord_guild_ids:
                    leave_msg = f"📍 {member.display_name or 'Unknown'} left the Discord Chat"
                    await self._send_to_telegram_text(mapping, leave_msg)
        self.telegram_app = ApplicationBuilder().token(self.config.telegram.token).build()
        self.telegram_app.add_handler(
            MessageHandler(filters.ALL & ~filters.COMMAND, self._handle_telegram)
        )
        await self.telegram_app.initialize()
        await self.telegram_app.start()
        await self.telegram_app.updater.start_polling()
        # Start endpoint polling for near-realtime message fetching
        endpoint_task = asyncio.create_task(self._poll_endpoint_periodically())
        def endpoint_task_exception_handler(task):
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self.logger.error(f"CRITICAL: Endpoint polling task crashed: {exc}", exc_info=True)
        endpoint_task.add_done_callback(endpoint_task_exception_handler)
        # Start donation polling task
        donation_task = asyncio.create_task(self._poll_latest_donation())
        def donation_task_exception_handler(task):
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                self.logger.error(f"CRITICAL: Donation polling task crashed: {exc}", exc_info=True)
        donation_task.add_done_callback(donation_task_exception_handler)
        discord_task = asyncio.create_task(self.discord_bot.start(self.config.discord.token))
        await self.discord_ready.wait()
        await discord_task
