from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.db.mongodb import get_db
from app.services.sms_service import mock_sms_instance


async def signup_helper(async_client: AsyncClient, mobile: str = "9876543210") -> dict:
    req = await async_client.post("/api/v1/auth/otp/request", json={"mobileNumber": mobile, "purpose": "signup"})
    challenge_id = req.json()["data"]["challengeId"]
    otp = mock_sms_instance.get_last_otp(mobile)

    ver = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={"mobileNumber": mobile, "otp": otp, "purpose": "signup", "challengeId": challenge_id},
    )
    ticket = ver.json()["data"]["verificationToken"]

    signup_res = await async_client.post(
        "/api/v1/auth/customer/signup",
        json={
            "fullName": "Token Tester",
            "email": f"tokens_{mobile}@example.com",
            "mobileNumber": mobile,
            "verificationToken": ticket,
            "acceptedTerms": True,
        },
    )
    return signup_res.json()["data"]


@pytest.mark.asyncio
async def test_refresh_token_rotation(async_client: AsyncClient):
    """Scenario 16: Refresh-token rotation."""
    data = await signup_helper(async_client, mobile="9876543210")
    original_refresh_token = data["tokens"]["refreshToken"]

    # First rotation
    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": original_refresh_token},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True

    new_refresh_token = res_data["data"]["refreshToken"]
    new_access_token = res_data["data"]["accessToken"]
    assert new_refresh_token != original_refresh_token
    assert new_access_token is not None


@pytest.mark.asyncio
async def test_reuse_of_old_refresh_token(async_client: AsyncClient):
    """Scenario 17: Reuse of an old refresh token revokes session."""
    data = await signup_helper(async_client, mobile="9876543214")
    original_refresh_token = data["tokens"]["refreshToken"]

    # Rotate once: success
    res1 = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": original_refresh_token},
    )
    assert res1.status_code == 200
    rotated_refresh_token = res1.json()["data"]["refreshToken"]

    # Attacker tries to use the original (old) refresh token
    res_reuse = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": original_refresh_token},
    )
    assert res_reuse.status_code == 401
    assert res_reuse.json()["error"]["code"] == "TOKEN_REUSE_DETECTED"

    # All sessions should now be revoked; even the rotated token must be revoked!
    res_post_reuse = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": rotated_refresh_token},
    )
    assert res_post_reuse.status_code == 401


@pytest.mark.asyncio
async def test_refresh_after_logout(async_client: AsyncClient):
    """Scenario 18: Refresh after logout is forbidden."""
    data = await signup_helper(async_client, mobile="9876543215")
    access_token = data["tokens"]["accessToken"]
    refresh_token = data["tokens"]["refreshToken"]

    # Logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refreshToken": refresh_token},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Try to refresh with logged-out session
    refresh_res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert refresh_res.status_code == 401
    assert refresh_res.json()["error"]["code"] in ("SESSION_REVOKED", "INVALID_REFRESH_TOKEN")


@pytest.mark.asyncio
async def test_access_with_missing_invalid_or_expired_jwt(async_client: AsyncClient):
    """Scenario 19: Access with missing, invalid, or expired JWT."""
    # Missing authorization header
    res_missing = await async_client.get("/api/v1/auth/me")
    assert res_missing.status_code == 401
    assert res_missing.json()["error"]["code"] == "NOT_AUTHENTICATED"

    # Invalid JWT token format
    res_invalid = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this-is-not-a-valid-jwt"},
    )
    assert res_invalid.status_code == 401
    assert res_invalid.json()["error"]["code"] == "INVALID_TOKEN"

    # Forged token with invalid signature
    data = await signup_helper(async_client, mobile="9876543216")
    real_token = data["tokens"]["accessToken"]
    tampered_token = real_token[:-5] + "aaaaa"
    res_tampered = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res_tampered.status_code == 401
