import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.logging import logger
from app.db.mongodb import mongo_manager


async def test_connection():
    print(f"Testing connection to MongoDB...")
    # Hide password from output
    safe_uri = settings.MONGODB_URI
    if "@" in safe_uri:
        prefix = safe_uri.split("@")[0].split("//")[0]
        host = safe_uri.split("@")[-1]
        print(f"Target URI: {prefix}//***:***@{host}")
    else:
        print(f"Target URI: {safe_uri}")

    try:
        await mongo_manager.connect(use_mock=False)
        is_alive = await mongo_manager.ping()
        if is_alive:
            print("[SUCCESS] MongoDB ping succeeded! Connected to real MongoDB.")
            supports_tx = await mongo_manager.supports_transactions()
            print(f"[SUCCESS] Multi-document transactions supported: {supports_tx}")
            db = mongo_manager.db
            collections = await db.list_collection_names()
            print(f"[INFO] Existing collections in '{settings.MONGODB_DATABASE}': {collections}")
        else:
            print("[ERROR] MongoDB ping returned False.")
    except Exception as exc:
        print(f"[ERROR] Failed to connect to MongoDB: {exc}")
    finally:
        await mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
