import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
import mongomock_motor
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.core.config import settings
from app.core.rate_limiter import get_rate_limiter
from app.db.indexes import create_indexes
from app.db.mongodb import mongo_manager
from app.main import app
from app.services.sms_service import mock_sms_instance


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def init_test_db():
    """Initialize mock MongoDB before tests and clear collections between tests."""
    settings.USE_MOCK_DB = True
    settings.APP_ENV = "testing"
    settings.DEBUG = True

    # Connect to in-memory mongomock_motor
    await mongo_manager.connect(use_mock=True, database_name="kirana_kart_test")
    await create_indexes()

    # Clear all collections
    db = mongo_manager.db
    collections = await db.list_collection_names()
    for col in collections:
        await db[col].delete_many({})

    # Clear SMS queue
    mock_sms_instance.clear()

    # Reset rate limiter
    limiter = get_rate_limiter()
    if hasattr(limiter, "reset"):
        await limiter.reset()

    yield

    # Teardown
    mock_sms_instance.clear()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client bound to the FastAPI ASGI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
