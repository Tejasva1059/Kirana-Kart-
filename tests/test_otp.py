from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.db.mongodb import get_db
from app.services.sms_service import mock_sms_instance


@pytest.mark.asyncio
async def test_valid_signup_otp_request(async_client: AsyncClient):
    """Scenario 1: Valid signup OTP request."""
    response = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert "challengeId" in res_data["data"]
    assert res_data["data"]["expiresIn"] == settings.OTP_EXPIRE_SECONDS
    assert res_data["data"]["resendAfter"] == settings.OTP_RESEND_COOLDOWN_SECONDS

    # Verify SMS was captured by mock provider without leaking in response
    last_otp = mock_sms_instance.get_last_otp("9876543210")
    assert last_otp is not None
    assert len(last_otp) == 6
    assert last_otp.isdigit()
    assert "otp" not in str(res_data).lower() or res_data["message"] != last_otp


@pytest.mark.asyncio
async def test_valid_login_otp_request(async_client: AsyncClient):
    """Scenario 2: Valid login OTP request for an active customer."""
    db = get_db()
    # Create an active customer first
    await db.customers.insert_one({
        "fullName": "Test Customer",
        "emailNormalized": "test@example.com",
        "mobileNumberNormalized": "9876543210",
        "role": "customer",
        "status": "active",
        "mobileVerified": True,
        "emailVerified": False,
        "acceptedTerms": True,
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    })

    response = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "login"},
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert "challengeId" in res_data["data"]

    # Verify SMS was dispatched
    last_otp = mock_sms_instance.get_last_otp("9876543210")
    assert last_otp is not None
    assert len(last_otp) == 6


@pytest.mark.asyncio
async def test_invalid_purpose_and_malformed_mobile(async_client: AsyncClient):
    """Scenario 3: Invalid purpose and malformed mobile number."""
    # Invalid purpose
    res1 = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "forgot_password"},
    )
    assert res1.status_code == 422
    assert res1.json()["success"] is False

    # Malformed mobile numbers
    bad_mobiles = ["12345", "abcdefghij", "5876543210", "+12345678901", ""]
    for bad_mobile in bad_mobiles:
        res = await async_client.post(
            "/api/v1/auth/otp/request",
            json={"mobileNumber": bad_mobile, "purpose": "signup"},
        )
        assert res.status_code in (400, 422)
        assert res.json()["success"] is False


@pytest.mark.asyncio
async def test_otp_expiration(async_client: AsyncClient):
    """Scenario 4: OTP expiration."""
    req_res = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    challenge_id = req_res.json()["data"]["challengeId"]
    otp = mock_sms_instance.get_last_otp("9876543210")

    # Manually backdate the challenge's expiresAt to the past
    db = get_db()
    past_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    await db.otp_challenges.update_one(
        {"challengeId": challenge_id},
        {"$set": {"expiresAt": past_time}},
    )

    verify_res = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "mobileNumber": "9876543210",
            "otp": otp,
            "purpose": "signup",
            "challengeId": challenge_id,
        },
    )
    assert verify_res.status_code == 400
    assert verify_res.json()["error"]["code"] in ("OTP_EXPIRED", "INVALID_OR_EXPIRED_OTP")


@pytest.mark.asyncio
async def test_incorrect_otp(async_client: AsyncClient):
    """Scenario 5: Incorrect OTP."""
    req_res = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    challenge_id = req_res.json()["data"]["challengeId"]

    verify_res = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "mobileNumber": "9876543210",
            "otp": "000000",
            "purpose": "signup",
            "challengeId": challenge_id,
        },
    )
    assert verify_res.status_code == 400
    assert verify_res.json()["error"]["code"] == "INCORRECT_OTP"


@pytest.mark.asyncio
async def test_maximum_otp_attempts(async_client: AsyncClient):
    """Scenario 6: Maximum OTP attempts."""
    req_res = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    challenge_id = req_res.json()["data"]["challengeId"]

    # Fail 5 times
    for i in range(5):
        verify_res = await async_client.post(
            "/api/v1/auth/otp/verify",
            json={
                "mobileNumber": "9876543210",
                "otp": f"99999{i}",
                "purpose": "signup",
                "challengeId": challenge_id,
            },
        )
        assert verify_res.status_code == 400

    assert verify_res.json()["error"]["code"] == "MAX_ATTEMPTS_EXCEEDED"

    # Even with correct OTP on the 6th attempt, it must be rejected
    correct_otp = mock_sms_instance.get_last_otp("9876543210")
    final_res = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "mobileNumber": "9876543210",
            "otp": correct_otp,
            "purpose": "signup",
            "challengeId": challenge_id,
        },
    )
    assert final_res.status_code == 400
    assert final_res.json()["error"]["code"] in ("MAX_ATTEMPTS_EXCEEDED", "OTP_INVALIDATED")


@pytest.mark.asyncio
async def test_otp_resend_cooldown(async_client: AsyncClient):
    """Scenario 7: OTP resend cooldown enforcement."""
    req1 = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    assert req1.status_code == 200

    # Immediate second request should be rejected by cooldown
    req2 = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    assert req2.status_code == 400
    assert req2.json()["error"]["code"] == "OTP_RESEND_COOLDOWN"


@pytest.mark.asyncio
async def test_otp_replay_prevention(async_client: AsyncClient):
    """Scenario 8: OTP replay prevention (cannot verify same OTP twice)."""
    req_res = await async_client.post(
        "/api/v1/auth/otp/request",
        json={"mobileNumber": "9876543210", "purpose": "signup"},
    )
    challenge_id = req_res.json()["data"]["challengeId"]
    otp = mock_sms_instance.get_last_otp("9876543210")

    # First verification: success
    v1 = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "mobileNumber": "9876543210",
            "otp": otp,
            "purpose": "signup",
            "challengeId": challenge_id,
        },
    )
    assert v1.status_code == 200
    assert "verificationToken" in v1.json()["data"]

    # Replay attempt: failure
    v2 = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={
            "mobileNumber": "9876543210",
            "otp": otp,
            "purpose": "signup",
            "challengeId": challenge_id,
        },
    )
    assert v2.status_code == 400
    assert v2.json()["error"]["code"] == "OTP_ALREADY_USED"


@pytest.mark.asyncio
async def test_sms_provider_failure(async_client: AsyncClient):
    """Scenario 26: SMS provider failure handling (503 Service Unavailable)."""
    with patch.object(mock_sms_instance, "send_otp", return_value=False):
        res = await async_client.post(
            "/api/v1/auth/otp/request",
            json={"mobileNumber": "9876543210", "purpose": "signup"},
        )
        assert res.status_code == 503
        assert res.json()["error"]["code"] == "SMS_DELIVERY_FAILED"
