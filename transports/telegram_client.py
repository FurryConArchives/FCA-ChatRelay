# Telegram transport client
from typing import Any, Tuple, List, Dict, Set, Optional

import asyncio

class TelegramClient:
    def __init__(self, bot, logger, blocked_usernames=None):
        self.bot = bot
        self.logger = logger
        self.blocked_usernames = set(u.lower() for u in (blocked_usernames or []))

    async def start(self):
        self.logger.info("Starting Telegram bot")
        await self.bot.initialize()
        await self.bot.start()

    async def send_message(self, mapping: Any, content: Optional[str], file_payloads: List[Tuple[bytes, str]], author_name: str):
        if author_name and author_name.lower() in self.blocked_usernames:
            return
        for chat_id in mapping.telegram_chat_id:
            try:
                if content:
                    await self.bot.send_message(chat_id=chat_id, text=content)
                for data, filename in file_payloads:
                    await self.bot.send_document(chat_id=chat_id, document=data, filename=filename)
            except Exception as exc:
                self.logger.error(f"Failed to send message to Telegram chat {chat_id}: {exc}", exc_info=True)

    async def fetch_endpoint_messages(self, chat_id: int, limit: int = 100) -> Tuple[List[Dict], Dict[int, str], Dict[int, str], Set[int]]:
        """Fetch messages from the archival endpoint. Returns (messages, user_name_map, user_username_map, bot_user_ids)."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://tg.tabs.gay/api/messages.getHistory"
                params = {"limit": limit, "page": 1, "peer": chat_id}
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status != 200:
                        self.logger.warning("Endpoint fetch failed for chat %s: %s", chat_id, response.status)
                        return [], {}, {}, set()
                    data = await response.json()
                    user_map: Dict[int, str] = {}
                    username_map: Dict[int, str] = {}
                    bot_user_ids: Set[int] = set()
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
                    return messages, user_map, username_map, bot_user_ids
        except asyncio.TimeoutError:
            self.logger.error(f"Endpoint fetch timeout for chat {chat_id}")
            return [], {}, {}, set()
        except Exception as exc:
            self.logger.error(f"Failed to fetch from endpoint for chat {chat_id}: {exc}", exc_info=True)
            return [], {}, {}, set()
