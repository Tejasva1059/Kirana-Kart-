import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_location_search_launch_area(async_client: AsyncClient):
    """Scenario: Search for launch location and verify serviceability."""
    res = await async_client.get("/api/v1/locations/search?q=Khudel")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    items = data["data"]["items"]
    assert len(items) > 0

    # Khudel must be marked as serviceable
    khudel_item = next((item for item in items if "khudel" in item["name"].lower()), None)
    assert khudel_item is not None
    assert khudel_item["isServiceable"] is True
    assert khudel_item["postalCode"] == "453115"
    assert khudel_item["location"]["latitude"] is not None
    assert khudel_item["location"]["longitude"] is not None


@pytest.mark.asyncio
async def test_location_search_outside_service_area(async_client: AsyncClient):
    """Scenario: Search for locations outside launch corridor marks isServiceable=False."""
    res = await async_client.get("/api/v1/locations/search?q=Palasia")
    assert res.status_code == 200
    data = res.json()["data"]
    items = data["items"]
    assert len(items) > 0
    palasia_item = items[0]
    assert palasia_item["isServiceable"] is False


@pytest.mark.asyncio
async def test_location_search_enforces_min_query_length(async_client: AsyncClient):
    """Scenario: Query less than 2 characters returns 400 BAD_REQUEST."""
    res = await async_client.get("/api/v1/locations/search?q=K")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "QUERY_TOO_SHORT"


@pytest.mark.asyncio
async def test_location_search_enforces_result_limits(async_client: AsyncClient):
    """Scenario: Search results obey limit query parameter up to max 20."""
    res = await async_client.get("/api/v1/locations/search?q=Indore&limit=2")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) <= 2


@pytest.mark.asyncio
async def test_location_search_does_not_leak_customer_saved_addresses(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Private customer address details (like recipient name or private note) are never returned in public location search."""
    secret_note = "SecretPrivateCustomerNote99"
    await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Confidential Home",
            "recipientName": "Vip Person",
            "recipientMobile": "9876543210",
            "addressLine1": "Top Secret Penthouse",
            "locality": secret_note,
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "deliveryInstructions": "Do not disclose",
        },
        headers=auth_headers["headers"],
    )

    # Search using public place search
    search_res = await async_client.get(f"/api/v1/locations/search?q={secret_note}")
    assert search_res.status_code == 200
    items = search_res.json()["data"]["items"]
    # Private customer address must NOT be returned in place search results
    assert len(items) == 0
