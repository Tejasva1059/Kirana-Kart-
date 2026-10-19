import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.core.rate_limiter import enforce_rate_limit, get_rate_limiter
from app.db.mongodb import mongo_manager
from app.services.sms_service import mock_sms_instance


@pytest.mark.asyncio
async def test_rate_limit_enforcement(async_client: AsyncClient):
    """Scenario 24: Rate-limit enforcement (429 Too Many Requests)."""
    # Trigger 11 requests when limit is 10
    limit_reached = False
    for i in range(12):
        res = await async_client.post(
            "/api/v1/auth/otp/request",
            json={"mobileNumber": f"98765432{i:02d}", "purpose": "signup"},
        )
        if res.status_code == 429:
            limit_reached = True
            assert res.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            break

    assert limit_reached, "Expected 429 Too Many Requests when exceeding rate limit."


@pytest.mark.asyncio
async def test_concurrent_otp_verification_attempts(async_client: AsyncClient):
    """Scenario 25: Concurrent OTP verification attempts with race condition protection."""
    req_res = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    challenge_id = req_res.json()["data"]["challengeId"]
    otp = mock_sms_instance.get_last_otp("9876543210")

    # Fire 5 concurrent verify requests with the identical valid OTP
    async def verify_task():
        return await async_client.post(
            "/api/v1/auth/otp/verify",
            json={
                "mobileNumber": "9876543210",
                "otp": otp,
                "purpose": "signup",
                "challengeId": challenge_id,
            },
        )

    responses = await asyncio.gather(*[verify_task() for _ in range(5)])

    # Exactly one request must succeed with 200, all other concurrent attempts must fail
    success_count = sum(1 for r in responses if r.status_code == 200)
    failure_count = sum(1 for r in responses if r.status_code != 200)

    assert success_count == 1, f"Expected exactly 1 verification success, got {success_count}"
    assert failure_count == 4, f"Expected 4 rejected concurrent attempts, got {failure_count}"


@pytest.mark.asyncio
async def test_health_and_readiness_probes(async_client: AsyncClient):
    """Liveness (/health) and readiness (/ready) checks."""
    # Liveness
    health_res = await async_client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "ok"
    assert "app" in health_res.json()

    # Readiness
    ready_res = await async_client.get("/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_mongodb_connection_failure_handling(async_client: AsyncClient):
    """Scenario 27: MongoDB connection failure handling (503 Service Unavailable on readiness)."""
    with patch.object(mongo_manager, "ping", new=AsyncMock(return_value=False)):
        # Temporarily set USE_MOCK_DB to False to test readiness failure
        original_mock_db = settings.USE_MOCK_DB
        try:
            settings.USE_MOCK_DB = False
            ready_res = await async_client.get("/ready")
            assert ready_res.status_code == 503
            assert ready_res.json()["status"] == "not_ready"
        finally:
            settings.USE_MOCK_DB = original_mock_db
