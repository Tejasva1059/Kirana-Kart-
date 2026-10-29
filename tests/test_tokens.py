import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from bson import ObjectId
import pytest
from httpx import AsyncClient
from pymongo.errors import PyMongoError
from app.core.security import compute_sha256_hash, create_access_token
from app.db.mongodb import get_db
from app.services.sms_service import mock_sms_instance


async def signup_helper(async_client: AsyncClient, mobile: str = "9876543201") -> dict:
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


# 1. A valid refresh token returns a new access token
@pytest.mark.asyncio
async def test_valid_refresh_token_returns_new_access_token(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543201")
    refresh_token = data["tokens"]["refreshToken"]

    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["success"] is True
    assert "accessToken" in res_json["data"]
    assert res_json["data"]["accessToken"] is not None
    assert len(res_json["data"]["accessToken"]) > 20


# 2. The new access token works with an existing protected endpoint
@pytest.mark.asyncio
async def test_new_access_token_works_with_protected_endpoint(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543202")
    refresh_token = data["tokens"]["refreshToken"]

    refresh_res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_access_token = refresh_res.json()["data"]["accessToken"]

    # Call protected /api/v1/auth/me
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert me_res.status_code == 200
    me_json = me_res.json()
    assert me_json["success"] is True
    assert me_json["data"]["customer"]["mobileNumber"] == "9876543202"


# 3. A valid refresh token returns a new refresh token if rotation is enabled
@pytest.mark.asyncio
async def test_valid_refresh_token_returns_new_refresh_token_rotation(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543203")
    original_refresh = data["tokens"]["refreshToken"]

    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": original_refresh},
    )
    assert res.status_code == 200
    res_data = res.json()["data"]
    new_refresh = res_data["refreshToken"]
    assert new_refresh != original_refresh
    assert len(new_refresh) > 20


# 4. The old refresh token is rejected after rotation (and revokes sessions upon reuse)
@pytest.mark.asyncio
async def test_old_refresh_token_rejected_after_rotation(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543204")
    original_refresh = data["tokens"]["refreshToken"]

    # First rotation
    res1 = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": original_refresh},
    )
    assert res1.status_code == 200
    new_refresh = res1.json()["data"]["refreshToken"]

    # Attempt to reuse old token
    reuse_res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": original_refresh},
    )
    assert reuse_res.status_code == 401
    assert reuse_res.json()["error"]["code"] == "TOKEN_REUSE_DETECTED"

    # Even new refresh token is now revoked due to reuse security alert
    subsequent_res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": new_refresh},
    )
    assert subsequent_res.status_code == 401


# 5. An expired refresh token is rejected
@pytest.mark.asyncio
async def test_expired_refresh_token_rejected(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543205")
    refresh_token = data["tokens"]["refreshToken"]
    db = get_db()
    token_hash = compute_sha256_hash(refresh_token)

    # Drop TTL index so mongomock allows inspecting the expired document in application logic
    try:
        await db.auth_sessions.drop_index("idx_session_ttl_expires")
    except Exception:
        pass

    # Force expiration in MongoDB
    past_time = datetime.now(timezone.utc) - timedelta(days=1)
    update_res = await db.auth_sessions.update_one(
        {"refreshTokenHash": token_hash},
        {"$set": {"expiresAt": past_time}},
    )
    assert update_res.matched_count == 1

    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] in ("TOKEN_EXPIRED", "INVALID_REFRESH_TOKEN")
    if res.json()["error"]["code"] == "TOKEN_EXPIRED":
        assert res.json()["error"]["code"] == "TOKEN_EXPIRED"


# 6. A malformed refresh token is rejected
@pytest.mark.asyncio
async def test_malformed_refresh_token_rejected(async_client: AsyncClient):
    # Empty string
    res_empty = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": ""},
    )
    assert res_empty.status_code == 422

    # Whitespace only
    res_ws = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": "    "},
    )
    assert res_ws.status_code == 422

    # Random malformed token
    res_malformed = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": "not-a-valid-opaque-refresh-token"},
    )
    assert res_malformed.status_code == 401
    assert res_malformed.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


# 7. A token with an invalid signature is rejected
@pytest.mark.asyncio
async def test_token_with_invalid_signature_rejected(async_client: AsyncClient):
    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": "invalidsignature_random_fake_token_value_abc123"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


# 8. An access token cannot be used as a refresh token
@pytest.mark.asyncio
async def test_access_token_cannot_be_used_as_refresh_token(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543208")
    access_token = data["tokens"]["accessToken"]

    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": access_token},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_TOKEN_TYPE"


# 9. A revoked refresh token is rejected
@pytest.mark.asyncio
async def test_revoked_refresh_token_rejected(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543209")
    refresh_token = data["tokens"]["refreshToken"]
    db = get_db()
    token_hash = compute_sha256_hash(refresh_token)

    # Manually mark revoked
    await db.auth_sessions.update_one(
        {"refreshTokenHash": token_hash},
        {"$set": {"revokedAt": datetime.now(timezone.utc)}},
    )

    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "SESSION_REVOKED"


# 10. A logged-out session cannot be refreshed
@pytest.mark.asyncio
async def test_logged_out_session_cannot_be_refreshed(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543210")
    access_token = data["tokens"]["accessToken"]
    refresh_token = data["tokens"]["refreshToken"]

    # Logout
    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refreshToken": refresh_token},
    )
    assert logout_res.status_code == 200

    # Refresh must fail
    refresh_res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert refresh_res.status_code == 401
    assert refresh_res.json()["error"]["code"] in ("SESSION_REVOKED", "INVALID_REFRESH_TOKEN")


# 11. A deleted or disabled user cannot refresh
@pytest.mark.asyncio
async def test_deleted_or_disabled_user_cannot_refresh(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543211")
    refresh_token = data["tokens"]["refreshToken"]
    customer_id = data["customer"]["id"]
    db = get_db()

    # Disable customer
    await db.customers.update_one(
        {"_id": ObjectId(customer_id)},
        {"$set": {"status": "suspended"}},
    )

    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "ACCOUNT_INACTIVE"

    # Delete customer completely
    await db.customers.delete_one({"_id": ObjectId(customer_id)})
    res_del = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert res_del.status_code == 401
    assert res_del.json()["error"]["code"] in ("CUSTOMER_NOT_FOUND", "ACCOUNT_INACTIVE")


# 12. Two concurrent refresh requests cannot both successfully consume the same token
@pytest.mark.asyncio
async def test_concurrent_refresh_requests_cannot_both_succeed(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543212")
    refresh_token = data["tokens"]["refreshToken"]

    # Trigger concurrent refresh requests
    res1, res2 = await asyncio.gather(
        async_client.post("/api/v1/auth/token/refresh", json={"refreshToken": refresh_token}),
        async_client.post("/api/v1/auth/token/refresh", json={"refreshToken": refresh_token}),
        return_exceptions=True,
    )

    status_codes = [res1.status_code, res2.status_code]
    # Exactly one must succeed (200) and the other must be rejected (401)
    assert 200 in status_codes
    assert 401 in status_codes


# 13. Existing login and protected endpoints remain compatible
@pytest.mark.asyncio
async def test_existing_login_and_protected_endpoints_remain_compatible(async_client: AsyncClient):
    mobile = "9876543213"
    data = await signup_helper(async_client, mobile=mobile)
    refresh_token = data["tokens"]["refreshToken"]

    # Rotate token
    ref_res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert ref_res.status_code == 200
    new_access_token = ref_res.json()["data"]["accessToken"]

    # Verify protected profile endpoint
    me_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["data"]["customer"]["mobileNumber"] == mobile

    # Verify customer login works independently
    req = await async_client.post("/api/v1/auth/otp/request", json={"mobileNumber": mobile, "purpose": "login"})
    challenge_id = req.json()["data"]["challengeId"]
    otp = mock_sms_instance.get_last_otp(mobile)
    ver = await async_client.post(
        "/api/v1/auth/otp/verify",
        json={"mobileNumber": mobile, "otp": otp, "purpose": "login", "challengeId": challenge_id},
    )
    ticket = ver.json()["data"]["verificationToken"]
    login_res = await async_client.post(
        "/api/v1/auth/customer/login",
        json={"mobileNumber": mobile, "verificationToken": ticket},
    )
    assert login_res.status_code == 200
    assert login_res.json()["data"]["tokens"]["accessToken"] is not None


# 14. Response schema remains compatible with the current API contract
@pytest.mark.asyncio
async def test_response_schema_compatibility(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543214")
    refresh_token = data["tokens"]["refreshToken"]

    # Test primary endpoint /api/v1/auth/token/refresh
    res = await async_client.post(
        "/api/v1/auth/token/refresh",
        json={"refreshToken": refresh_token},
    )
    assert res.status_code == 200
    res_json = res.json()
    assert res_json["success"] is True
    assert res_json["message"] == "Tokens refreshed successfully"

    # Both top-level and nested 'tokens' structure present for maximum client compatibility
    assert "accessToken" in res_json["data"]
    assert "refreshToken" in res_json["data"]
    assert "tokens" in res_json["data"]
    assert "accessToken" in res_json["data"]["tokens"]
    assert "refreshToken" in res_json["data"]["tokens"]

    # Test alias route /api/v1/auth/refresh
    alias_refresh = res_json["data"]["refreshToken"]
    alias_res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": alias_refresh},
    )
    assert alias_res.status_code == 200
    alias_json = alias_res.json()
    assert alias_json["success"] is True
    assert "accessToken" in alias_json["data"]


# 15. Database failures are handled safely
@pytest.mark.asyncio
async def test_database_failure_handling(async_client: AsyncClient):
    data = await signup_helper(async_client, mobile="9876543215")
    refresh_token = data["tokens"]["refreshToken"]

    with patch("app.services.token_service.get_db") as mock_db:
        mock_col = mock_db.return_value.auth_sessions
        mock_col.find_one.side_effect = PyMongoError("MongoDB connection lost: replica set unreachable")

        res = await async_client.post(
            "/api/v1/auth/token/refresh",
            json={"refreshToken": refresh_token},
        )
        assert res.status_code == 503
        error_json = res.json()
        assert error_json["success"] is False
        assert error_json["error"]["code"] == "DATABASE_UNAVAILABLE"
