import pytest
from httpx import AsyncClient
from app.services.sms_service import mock_sms_instance


async def signup_customer(async_client: AsyncClient, mobile: str = "9876543210") -> dict:
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
            "fullName": "Original Name",
            "email": f"profile_{mobile}@example.com",
            "mobileNumber": mobile,
            "verificationToken": ticket,
            "acceptedTerms": True,
        },
    )
    return signup_res.json()["data"]


@pytest.mark.asyncio
async def test_fetch_authenticated_profile(async_client: AsyncClient):
    """Scenario 20: Fetch profile for authenticated customer."""
    data = await signup_customer(async_client, mobile="9876543210")
    access_token = data["tokens"]["accessToken"]

    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True

    customer = res_data["data"]["customer"]
    assert customer["fullName"] == "Original Name"
    assert customer["mobileNumber"] == "9876543210"
    assert customer["email"] == "profile_9876543210@example.com"
    assert customer["role"] == "customer"
    assert customer["status"] == "active"


@pytest.mark.asyncio
async def test_update_permitted_profile_fields(async_client: AsyncClient):
    """Scenario 21: Update permitted profile fields (fullName, email)."""
    data = await signup_customer(async_client, mobile="9876543211")
    access_token = data["tokens"]["accessToken"]

    update_res = await async_client.patch(
        "/api/v1/customers/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "fullName": "Updated New Name",
            "email": "updated_email@example.com",
        },
    )
    assert update_res.status_code == 200
    res_data = update_res.json()
    assert res_data["success"] is True

    customer = res_data["data"]["customer"]
    assert customer["fullName"] == "Updated New Name"
    assert customer["email"] == "updated_email@example.com"

    # Verify fetched profile reflects updates
    get_res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert get_res.json()["data"]["customer"]["fullName"] == "Updated New Name"


@pytest.mark.asyncio
async def test_reject_updates_to_protected_fields(async_client: AsyncClient):
    """Scenario 22: Reject updates to protected fields (role, status, _id, etc.)."""
    data = await signup_customer(async_client, mobile="9876543212")
    access_token = data["tokens"]["accessToken"]

    # Attempt to change role to admin
    res_role = await async_client.patch(
        "/api/v1/customers/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"role": "admin"},
    )
    assert res_role.status_code in (400, 422)

    # Attempt to change status
    res_status = await async_client.patch(
        "/api/v1/customers/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"status": "suspended"},
    )
    assert res_status.status_code in (400, 422)

    # Empty update body rejected
    res_empty = await async_client.patch(
        "/api/v1/customers/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={},
    )
    assert res_empty.status_code in (400, 422)


@pytest.mark.asyncio
async def test_reject_mobile_number_change_without_otp(async_client: AsyncClient):
    """Scenario 23: Reject attempt to change mobile number without OTP verification."""
    data = await signup_customer(async_client, mobile="9876543213")
    access_token = data["tokens"]["accessToken"]

    res_mobile = await async_client.patch(
        "/api/v1/customers/me",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"mobileNumber": "9876543299"},
    )
    assert res_mobile.status_code in (400, 422)
    err = res_mobile.json()
    assert err["success"] is False
