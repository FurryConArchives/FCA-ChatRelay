import asyncio
from typing import Any

class TelegramPoller:
    def __init__(self, config, state_repo, router, telegram_client, logger):
        self.config = config
        self.state_repo = state_repo
        self.router = router
        self.telegram_client = telegram_client
        self.logger = logger
        self._running = False

    async def start(self):
        await asyncio.sleep(2)
        poll_count = 0
        self._running = True
        while self._running:
            try:
                poll_count += 1
                for mapping in self.config.bridges:
                    try:
                        for chat_id in mapping.telegram_chat_id:
                            try:
                                # Fetch messages from Telegram endpoint via telegram_client
                                messages, user_map, username_map, bot_user_ids = await self.telegram_client.fetch_endpoint_messages(chat_id, limit=15)
                                self.logger.debug(f"[Poll #{poll_count}] Fetched {len(messages)} messages for chat_id={chat_id}")
                                for msg in reversed(messages):
                                    try:
                                        msg_id = msg.get("id")
                                        # Deduplication
                                        processed = self.state_repo.load_processed()
                                        if chat_id in processed and msg_id in processed[chat_id]:
                                            continue
                                        # Route message for relay
                                        await self.router.relay_telegram_to_discord(mapping, msg, user_map, username_map, bot_user_ids, chat_id)
                                        self.state_repo.save_processed(chat_id, msg_id)
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
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                self.logger.info("Polling task cancelled")
                self._running = False
                raise
            except Exception as exc:
                self.logger.error(f"Unexpected error in polling loop: {exc}", exc_info=True)
                await asyncio.sleep(10)
