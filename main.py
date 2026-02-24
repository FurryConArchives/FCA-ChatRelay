import asyncio
import logging
from src.bridge.bridge import BridgeApp

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = BridgeApp("config.json")
    asyncio.run(app.start())

if __name__ == "__main__":
    main()
