# Main entrypoint for modular bridge
from core.config import AppConfig, load_config
from storage.state_repository import StateRepository, MessageMapRepository
from services.media_handler import MediaHandler
from core.message_router import MessageRouter
from transports.discord_client import DiscordClient
from transports.telegram_client import TelegramClient
from transports.fluxer_client import FluxerClient
from services.telegram_poller import TelegramPoller
from services.donation_poller import DonationPoller
import logging
import asyncio
import json
import sys
import os

# --- Real bot imports ---
import discord
from discord.ext import commands
from telegram.ext import ApplicationBuilder
import fluxer


class BridgeApp:
    def __init__(self, config: AppConfig):
        self.config = config
        # Main logger for app-wide events
        self.logger = logging.getLogger("FCAMultiBridge")
        self.discord_logger = self.logger.getChild("Discord")
        self.telegram_logger = self.logger.getChild("Telegram")
        self.fluxer_logger = self.logger.getChild("Fluxer")

        self.state_repo = StateRepository("bridge_state.db")
        self.msgmap_repo = MessageMapRepository("bridge_state.db")
        self.media = MediaHandler()

        # --- Bot inits --
        discord_bot = commands.Bot(intents=discord.Intents.all())
        telegram_bot = ApplicationBuilder().token(config.telegram.token).build()
        fluxer_bot = fluxer.Bot(intents=fluxer.Intents.all())
        self.discord = DiscordClient(discord_bot, self.discord_logger)
        self.telegram = TelegramClient(telegram_bot, self.telegram_logger)
        self.router = MessageRouter(config, self.discord, self.media, self.logger, self.telegram, self.msgmap_repo)
        self.fluxer = FluxerClient(fluxer_bot, self.fluxer_logger, self.router)
        self.router = MessageRouter(config, self.discord, self.media, self.logger, self.telegram, self.msgmap_repo)
        self.telegram_poller = TelegramPoller(config, self.state_repo, self.router, self.telegram, self.logger)
        self.donation_poller = DonationPoller(config, self.router, self.logger)

    async def start(self):
        # Start only enabled bots and pollers concurrently
        tasks = []
        if self.config.discord.enabled:
            tasks.append(asyncio.create_task(self.discord.start(self.config.discord.token)))
        if self.config.telegram.enabled:
            tasks.append(asyncio.create_task(self.telegram.start()))
        if self.config.fluxer.enabled:
            tasks.append(asyncio.create_task(self.fluxer.start(self.config.fluxer.token)))
        tasks.append(asyncio.create_task(self.telegram_poller.start()))
        tasks.append(asyncio.create_task(self.donation_poller.start()))
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    
    # Suppress noisy INFO logs from third-party libraries
    logging.getLogger("discord").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    logging.getLogger("telegram").setLevel(logging.CRITICAL)
    logging.getLogger("apscheduler").setLevel(logging.CRITICAL)
    #logging.getLogger("fluxer").setLevel(logging.CRITICAL)

    config_path = os.environ.get("BRIDGE_CONFIG", "config.json")
    config = load_config(config_path)
    enabled_services = [
        config.discord.enabled,
        config.telegram.enabled,
        config.fluxer.enabled
    ]
    if enabled_services.count(True) <= 1:
        logging.error("You must enable at least two services for bridging to function. Exiting.")
        sys.exit(1)
    app = BridgeApp(config)
    asyncio.run(app.start())
