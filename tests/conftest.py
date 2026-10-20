import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict
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


@pytest_asyncio.fixture
async def auth_headers() -> Dict[str, Any]:
    """Create test customer and return valid Bearer auth headers."""
    from bson import ObjectId
    from app.services.token_service import TokenService
    db = mongo_manager.db
    now = datetime.now(timezone.utc)
    cust_id = ObjectId()
    customer_doc = {
        "_id": cust_id,
        "fullName": "Test Customer",
        "mobileNumberNormalized": "9876543210",
        "emailNormalized": "testcustomer@example.com",
        "role": "customer",
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    }
    await db.customers.insert_one(customer_doc)
    tokens = await TokenService.create_session_and_tokens(customer_id=str(cust_id), role="customer")
    return {
        "headers": {"Authorization": f"Bearer {tokens.accessToken}"},
        "customer_id": str(cust_id),
        "customer": customer_doc,
    }


@pytest_asyncio.fixture
async def auth_headers_other() -> Dict[str, Any]:
    """Create a second distinct customer for cross-customer authorization testing."""
    from bson import ObjectId
    from app.services.token_service import TokenService
    db = mongo_manager.db
    now = datetime.now(timezone.utc)
    cust_id = ObjectId()
    customer_doc = {
        "_id": cust_id,
        "fullName": "Other Customer",
        "mobileNumberNormalized": "9123456789",
        "emailNormalized": "othercustomer@example.com",
        "role": "customer",
        "status": "active",
        "createdAt": now,
        "updatedAt": now,
    }
    await db.customers.insert_one(customer_doc)
    tokens = await TokenService.create_session_and_tokens(customer_id=str(cust_id), role="customer")
    return {
        "headers": {"Authorization": f"Bearer {tokens.accessToken}"},
        "customer_id": str(cust_id),
        "customer": customer_doc,
    }

