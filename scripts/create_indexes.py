import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.logging import logger
from app.db.indexes import create_indexes
from app.db.mongodb import mongo_manager


async def main() -> None:
    logger.info("Connecting to MongoDB to initialize collection indexes...")
    await mongo_manager.connect()
    try:
        await create_indexes()
        logger.info("Indexes successfully initialized!")
    finally:
        await mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
