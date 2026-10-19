from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from app.db.mongodb import get_db
from app.services.sms_service import mock_sms_instance


async def create_active_customer(mobile: str = "9876543210", email: str = "login@example.com", status: str = "active") -> str:
    db = get_db()
    res = await db.customers.insert_one({
        "fullName": "Login Tester",
        "emailNormalized": email,
        "mobileNumberNormalized": mobile,
        "role": "customer",
        "status": status,
        "mobileVerified": True,
        "emailVerified": False,
        "acceptedTerms": True,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })
    return str(res.inserted_id)


async def get_login_ticket(async_client: AsyncClient, mobile: str = "9876543210") -> str:
    req_res = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": mobile, "purpose": "login"},
    )
    challenge_id = req_res.json()["data"]["challengeId"]
    otp = mock_sms_instance.get_last_otp(mobile)

    ver_res = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "mobileNumber": mobile,
            "otp": otp,
            "purpose": "login",
            "challengeId": challenge_id,
        },
    )
    return ver_res.json()["data"]["verificationToken"]


@pytest.mark.asyncio
async def test_successful_login(async_client: AsyncClient):
    """Scenario 14: Successful login with valid ticket."""
    await create_active_customer(mobile="9876543210")
    ticket = await get_login_ticket(async_client, mobile="9876543210")

    login_res = await async_client.post(
        "/api/v1/auth/customer/login",
        json={
            "mobileNumber": "9876543210",
            "verificationToken": ticket,
        },
    )
    assert login_res.status_code == 200
    res_data = login_res.json()
    assert res_data["success"] is True

    customer = res_data["data"]["customer"]
    assert customer["mobileNumber"] == "9876543210"
    assert customer["status"] == "active"

    tokens = res_data["data"]["tokens"]
    assert "accessToken" in tokens
    assert "refreshToken" in tokens
    assert tokens["tokenType"] == "Bearer"


@pytest.mark.asyncio
async def test_login_for_nonexistent_or_blocked_customer(async_client: AsyncClient):
    """Scenario 15: Login for nonexistent or blocked customer."""
    # Nonexistent mobile OTP request: generic response returned without SMS
    res_none = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9999999999", "purpose": "login"},
    )
    assert res_none.status_code == 200
    assert mock_sms_instance.get_last_otp("9999999999") is None  # No SMS sent!

    # Blocked customer
    await create_active_customer(mobile="9876543213", email="blocked@example.com", status="blocked")
    res_blocked_otp = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543213", "purpose": "login"},
    )
    assert res_blocked_otp.status_code == 200
    assert mock_sms_instance.get_last_otp("9876543213") is None  # Suppressed!

    # Attempt direct login with a forged/nonexistent ticket
    bad_login = await async_client.post(
        "/api/v1/auth/customer/login",
        json={
            "mobileNumber": "9876543213",
            "verificationToken": "fake-ticket",
        },
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["error"]["code"] == "INVALID_VERIFICATION_TICKET"


@pytest.mark.asyncio
async def test_login_ticket_replay_prevention(async_client: AsyncClient):
    """Login ticket can only be used once."""
    await create_active_customer(mobile="9876543210")
    ticket = await get_login_ticket(async_client, mobile="9876543210")

    # First login: OK
    res1 = await async_client.post(
        "/api/v1/auth/customer/login",
        json={"mobileNumber": "9876543210", "verificationToken": ticket},
    )
    assert res1.status_code == 200

    # Replay: 401 Unauthorized
    res2 = await async_client.post(
        "/api/v1/auth/customer/login",
        json={"mobileNumber": "9876543210", "verificationToken": ticket},
    )
    assert res2.status_code == 401
    assert res2.json()["error"]["code"] == "INVALID_VERIFICATION_TICKET"
