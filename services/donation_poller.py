import asyncio
import aiohttp

class DonationPoller:
    def __init__(self, config, router, logger):
        self.config = config
        self.router = router
        self.logger = logger
        self._running = False

    async def start(self):
        last_donation_id = None
        self._running = True
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    url = "https://furryconarchives.org/api/latest-donation"
                    async with session.get(url, timeout=10) as response:
                        if response.status != 200:
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
                        await self.router.relay_donation_alert(name, float(amount), message)
                        self.logger.info(f"Donation alert sent: {message}")
            except Exception as exc:
                self.logger.error(f"Error polling latest donation: {exc}", exc_info=True)
            await asyncio.sleep(60)
