import pytest
from httpx import AsyncClient
from app.db.mongodb import mongo_manager


@pytest.mark.asyncio
async def test_serviceability_check_request_a_saved_address(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Check delivery eligibility for a saved address (Request A)."""
    # Create saved address in Khudel
    create_res = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Launch Area Home",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Near Main Market",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    addr_id = create_res.json()["data"]["id"]

    res = await async_client.post(
        "/api/v1/serviceability/check",
        json={"addressId": addr_id},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["isServiceable"] is True
    assert data["serviceAreaId"] == "indore-launch-area"
    assert data["deliveryCharge"] == 0
    assert data["currency"] == "INR"
    assert data["reasonCode"] == "WITHIN_SERVICE_AREA"


@pytest.mark.asyncio
async def test_serviceability_check_request_b_coordinates(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Check delivery eligibility directly using coordinates (Request B)."""
    # Coordinates inside Khudel corridor: 75.9782, 22.6841
    res = await async_client.post(
        "/api/v1/serviceability/check",
        json={
            "location": {
                "latitude": 22.6841,
                "longitude": 75.9782,
            }
        },
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["isServiceable"] is True
    assert data["reasonCode"] == "WITHIN_SERVICE_AREA"
    assert data["deliveryCharge"] == 0


@pytest.mark.asyncio
async def test_serviceability_check_request_c_postal_and_locality(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Check delivery eligibility using postal code and locality before saving (Request C)."""
    # Test Index Medical College
    res = await async_client.post(
        "/api/v1/serviceability/check",
        json={
            "postalCode": "452016",
            "city": "Indore",
            "locality": "Index Medical College",
        },
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["isServiceable"] is True
    assert data["serviceAreaId"] == "indore-launch-area"
    assert data["deliveryCharge"] == 0


@pytest.mark.asyncio
async def test_serviceability_ineligible_location(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Location outside configured service areas returns isServiceable=False."""
    # Delhi coordinates: 77.2090, 28.6139, PIN 110001
    res = await async_client.post(
        "/api/v1/serviceability/check",
        json={
            "postalCode": "110001",
            "city": "New Delhi",
            "locality": "Connaught Place",
            "location": {
                "latitude": 28.6139,
                "longitude": 77.2090,
            },
        },
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["isServiceable"] is False
    assert data["serviceAreaId"] is None
    assert data["reasonCode"] == "OUTSIDE_SERVICE_AREA"
    assert data["deliveryCharge"] is None


@pytest.mark.asyncio
async def test_serviceability_check_cross_customer_address_rejected(async_client: AsyncClient, auth_headers: dict, auth_headers_other: dict):
    """Scenario: Cannot check serviceability using another customer's addressId."""
    create_res = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Private Home",
            "recipientName": "Customer One",
            "recipientMobile": "9876543210",
            "addressLine1": "P1",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    addr_id = create_res.json()["data"]["id"]

    res_other = await async_client.post(
        "/api/v1/serviceability/check",
        json={"addressId": addr_id},
        headers=auth_headers_other["headers"],
    )
    assert res_other.status_code == 404


@pytest.mark.asyncio
async def test_serviceability_when_service_areas_disabled(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Returns SERVICE_AREA_NOT_CONFIGURED when no enabled service areas exist."""
    from app.services.serviceability_service import ServiceabilityService
    await ServiceabilityService.seed_default_service_areas_if_needed()
    db = mongo_manager.db
    # Temporarily disable all service areas
    await db.service_areas.update_many({}, {"$set": {"enabled": False}})

    res = await async_client.post(
        "/api/v1/serviceability/check",
        json={"postalCode": "453115", "locality": "Khudel"},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["isServiceable"] is False
    assert data["reasonCode"] == "SERVICE_AREA_NOT_CONFIGURED"

    # Re-enable
    await db.service_areas.update_many({}, {"$set": {"enabled": True}})
