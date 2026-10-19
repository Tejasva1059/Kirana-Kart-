from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from app.db.mongodb import get_db
from app.services.sms_service import mock_sms_instance


async def get_signup_ticket(async_client: AsyncClient, mobile: str = "9876543210") -> str:
    """Helper to request and verify OTP for signup, returning the verification ticket."""
    req_res = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": mobile, "purpose": "signup"},
    )
    challenge_id = req_res.json()["data"]["challengeId"]
    otp = mock_sms_instance.get_last_otp(mobile)

    ver_res = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "mobileNumber": mobile,
            "otp": otp,
            "purpose": "signup",
            "challengeId": challenge_id,
        },
    )
    return ver_res.json()["data"]["verificationToken"]


async def get_login_ticket(async_client: AsyncClient, mobile: str = "9876543210") -> str:
    """Helper to request and verify OTP for login, returning the verification ticket."""
    db = get_db()
    # Ensure customer exists so login OTP will issue
    existing = await db.customers.find_one({"mobileNumberNormalized": mobile})
    if not existing:
        await db.customers.insert_one({
            "fullName": "Pre-existing Customer",
            "emailNormalized": f"cust_{mobile}@example.com",
            "mobileNumberNormalized": mobile,
            "role": "customer",
            "status": "active",
            "mobileVerified": True,
            "emailVerified": False,
            "acceptedTerms": True,
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
        })

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
async def test_signup_without_verification_ticket(async_client: AsyncClient):
    """Scenario 9: Signup without a valid verification ticket."""
    res = await async_client.post(
        "/api/v1/auth/customer/signup",
        json={
            "fullName": "Rahul Sharma",
            "email": "rahul@example.com",
            "mobileNumber": "9876543210",
            "verificationToken": "invalid-or-fake-ticket",
            "acceptedTerms": True,
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_VERIFICATION_TICKET"


@pytest.mark.asyncio
async def test_signup_using_login_purpose_ticket(async_client: AsyncClient):
    """Scenario 10: Signup using a ticket issued for login purpose."""
    login_ticket = await get_login_ticket(async_client, mobile="9876543210")

    res = await async_client.post(
        "/api/v1/auth/customer/signup",
        json={
            "fullName": "Rahul Sharma",
            "email": "rahul@example.com",
            "mobileNumber": "9876543210",
            "verificationToken": login_ticket,
            "acceptedTerms": True,
        },
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_TICKET_PURPOSE"


@pytest.mark.asyncio
async def test_successful_signup(async_client: AsyncClient):
    """Scenario 11: Successful customer registration."""
    ticket = await get_signup_ticket(async_client, mobile="9876543210")

    res = await async_client.post(
        "/api/v1/auth/customer/signup",
        json={
            "fullName": "Rahul Sharma",
            "email": "rahul@example.com",
            "mobileNumber": "9876543210",
            "verificationToken": ticket,
            "acceptedTerms": True,
        },
    )
    assert res.status_code == 201
    res_data = res.json()
    assert res_data["success"] is True

    customer = res_data["data"]["customer"]
    assert customer["fullName"] == "Rahul Sharma"
    assert customer["email"] == "rahul@example.com"
    assert customer["mobileNumber"] == "9876543210"
    assert customer["role"] == "customer"
    assert customer["status"] == "active"
    assert "id" in customer

    tokens = res_data["data"]["tokens"]
    assert "accessToken" in tokens
    assert "refreshToken" in tokens
    assert tokens["tokenType"] == "Bearer"
    assert tokens["expiresIn"] == 900


@pytest.mark.asyncio
async def test_duplicate_mobile_and_duplicate_email(async_client: AsyncClient):
    """Scenario 12: Duplicate mobile and duplicate email enforcement."""
    # First signup
    ticket1 = await get_signup_ticket(async_client, mobile="9876543210")
    res1 = await async_client.post(
        "/api/v1/auth/customer/signup",
        json={
            "fullName": "Customer One",
            "email": "unique@example.com",
            "mobileNumber": "9876543210",
            "verificationToken": ticket1,
            "acceptedTerms": True,
        },
    )
    assert res1.status_code == 201

    # Second signup with same mobile should fail before or during signup
    # Requesting signup OTP for existing mobile must fail
    res_otp_conflict = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    assert res_otp_conflict.status_code == 409
    assert res_otp_conflict.json()["error"]["code"] == "ACCOUNT_ALREADY_EXISTS"

    # Second signup with different mobile but duplicate email
    ticket2 = await get_signup_ticket(async_client, mobile="9876543211")
    res2 = await async_client.post(
        "/api/v1/auth/customer/signup",
        json={
            "fullName": "Customer Two",
            "email": "unique@example.com",  # Duplicate email!
            "mobileNumber": "9876543211",
            "verificationToken": ticket2,
            "acceptedTerms": True,
        },
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_public_signup_cannot_assign_privileged_roles(async_client: AsyncClient):
    """Scenario 13: Public signup cannot assign admin, vendor, or rider role."""
    ticket = await get_signup_ticket(async_client, mobile="9876543212")

    # Attempting to supply role: admin, status: blocked, _id: custom
    res = await async_client.post(
        "/api/v1/auth/customer/signup",
        json={
            "fullName": "Hacker Sharma",
            "email": "hacker@example.com",
            "mobileNumber": "9876543212",
            "verificationToken": ticket,
            "acceptedTerms": True,
            "role": "admin",  # Forbidden extra field
        },
    )
    # Pydantic extra='forbid' rejects extra fields with 422
    assert res.status_code == 422
    assert res.json()["success"] is False
