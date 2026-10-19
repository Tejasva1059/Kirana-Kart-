from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import settings
from app.core.logging import logger

try:
    import mongomock_motor
except ImportError:
    mongomock_motor = None


try:
    import certifi
except ImportError:
    certifi = None


class MongoManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    _supports_transactions: Optional[bool] = None

    async def connect(self, uri: Optional[str] = None, database_name: Optional[str] = None, use_mock: Optional[bool] = None) -> None:
        target_uri = uri or settings.MONGODB_URI
        target_db = database_name or settings.MONGODB_DATABASE
        is_mock = use_mock if use_mock is not None else settings.USE_MOCK_DB

        if is_mock:
            if mongomock_motor is None:
                raise RuntimeError("mongomock_motor is required for mock database mode.")
            logger.info("Initializing in-memory mongomock_motor database client.")
            self.client = mongomock_motor.AsyncMongoMockClient()
            self.db = self.client[target_db]
            self._supports_transactions = False
            return

        logger.info(f"Connecting to MongoDB at {target_uri.split('@')[-1] if '@' in target_uri else target_uri}")
        client_kwargs = {
            "minPoolSize": settings.MONGODB_MIN_POOL_SIZE,
            "maxPoolSize": settings.MONGODB_MAX_POOL_SIZE,
            "serverSelectionTimeoutMS": 10000,
            "uuidRepresentation": "standard",
        }
        if certifi:
            client_kwargs["tlsCAFile"] = certifi.where()

        self.client = AsyncIOMotorClient(
            target_uri,
            **client_kwargs,
        )
        self.db = self.client[target_db]

    async def close(self) -> None:
        if self.client:
            logger.info("Closing MongoDB connection.")
            self.client.close()
            self.client = None
            self.db = None
            self._supports_transactions = None

    async def ping(self) -> bool:
        if not self.client:
            return False
        try:
            # Check server availability
            await self.client.admin.command("ping")
            return True
        except Exception as exc:
            logger.warning(f"MongoDB ping check failed: {exc}")
            return False

    async def supports_transactions(self) -> bool:
        """Check whether the connected MongoDB instance supports multi-document transactions."""
        if self._supports_transactions is not None:
            return self._supports_transactions
        if not self.client:
            return False
        try:
            res = await self.client.admin.command("isMaster")
            # Replica set or mongos supports transactions
            has_replica = bool(res.get("setName") or res.get("msg") == "isdbgrid")
            self._supports_transactions = has_replica
            return has_replica
        except Exception:
            self._supports_transactions = False
            return False


mongo_manager = MongoManager()


def get_db() -> AsyncIOMotorDatabase:
    if mongo_manager.db is None:
        raise RuntimeError("MongoDB connection is not initialized. Ensure startup event ran.")
    return mongo_manager.db
