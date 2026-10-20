import asyncio
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from bson import ObjectId
from app.db.mongodb import mongo_manager


@pytest.mark.asyncio
async def test_list_addresses_empty(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Return empty list when no addresses exist."""
    res = await async_client.get("/api/v1/addresses", headers=auth_headers["headers"])
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["data"]["items"] == []
    assert data["data"]["total"] == 0


@pytest.mark.asyncio
async def test_create_first_address_auto_default(async_client: AsyncClient, auth_headers: dict):
    """Scenario: First created address is automatically assigned as default."""
    payload = {
        "label": "Home",
        "recipientName": "Rahul Sharma",
        "recipientMobile": "9876543210",
        "addressLine1": "Plot 14, Main Road",
        "locality": "Khudel",
        "city": "Indore",
        "district": "Indore",
        "state": "Madhya Pradesh",
        "postalCode": "453115",
        "country": "India",
        "isDefault": False,  # Even if sent False, first address must become True
    }
    res = await async_client.post("/api/v1/addresses", json=payload, headers=auth_headers["headers"])
    assert res.status_code == 201
    data = res.json()["data"]
    assert data["isDefault"] is True
    assert data["label"] == "Home"
    assert data["recipientName"] == "Rahul Sharma"
    assert data["serviceability"]["isServiceable"] is True
    assert data["serviceability"]["deliveryCharge"] == 0


@pytest.mark.asyncio
async def test_create_second_address_without_changing_default(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Creating another address without isDefault=True leaves original default unchanged."""
    # First address
    res1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Home",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 14",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    first_id = res1.json()["data"]["id"]

    # Second address
    res2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Work",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Office Block B",
            "locality": "Index Medical College",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "452016",
            "isDefault": False,
        },
        headers=auth_headers["headers"],
    )
    assert res2.status_code == 201
    second_id = res2.json()["data"]["id"]
    assert res2.json()["data"]["isDefault"] is False

    # Check list: first must remain default
    list_res = await async_client.get("/api/v1/addresses", headers=auth_headers["headers"])
    items = list_res.json()["data"]["items"]
    assert len(items) == 2
    assert items[0]["id"] == first_id
    assert items[0]["isDefault"] is True


@pytest.mark.asyncio
async def test_create_address_as_default_unsets_previous_default(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Creating an address with isDefault=True unsets previous default."""
    res1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Home",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 14",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    first_id = res1.json()["data"]["id"]

    # Create second with isDefault=True
    res2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Work",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Office Block B",
            "locality": "Doublechowki",
            "city": "Dewas",
            "district": "Dewas",
            "state": "Madhya Pradesh",
            "postalCode": "455223",
            "isDefault": True,
        },
        headers=auth_headers["headers"],
    )
    second_id = res2.json()["data"]["id"]
    assert res2.json()["data"]["isDefault"] is True

    # Verify first is now false
    get_res1 = await async_client.get(f"/api/v1/addresses/{first_id}", headers=auth_headers["headers"])
    assert get_res1.json()["data"]["isDefault"] is False

    # List: default comes first
    list_res = await async_client.get("/api/v1/addresses", headers=auth_headers["headers"])
    items = list_res.json()["data"]["items"]
    assert items[0]["id"] == second_id
    assert items[0]["isDefault"] is True


@pytest.mark.asyncio
async def test_get_address_ownership_isolation(async_client: AsyncClient, auth_headers: dict, auth_headers_other: dict):
    """Scenario: Customer cannot read another customer's address (returns 404)."""
    # Customer 1 creates address
    res = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Secret Location",
            "recipientName": "Customer One",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 99",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    addr_id = res.json()["data"]["id"]

    # Customer 2 attempts to fetch it
    res_other = await async_client.get(f"/api/v1/addresses/{addr_id}", headers=auth_headers_other["headers"])
    assert res_other.status_code == 404
    assert res_other.json()["error"]["code"] == "ADDRESS_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_address_permitted_fields(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Update permitted address fields."""
    create_res = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Old Home",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 10",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    addr_id = create_res.json()["data"]["id"]

    update_res = await async_client.patch(
        f"/api/v1/addresses/{addr_id}",
        json={
            "label": "Renovated Home",
            "addressLine1": "Villa 10-A",
            "landmark": "Near Shiv Temple",
        },
        headers=auth_headers["headers"],
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()["data"]
    assert updated_data["label"] == "Renovated Home"
    assert updated_data["addressLine1"] == "Villa 10-A"
    assert "Near Shiv Temple" in updated_data["formattedAddress"]


@pytest.mark.asyncio
async def test_update_address_rejects_protected_fields(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Reject modifications to protected fields (forbid extra fields)."""
    create_res = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Home",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 10",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    addr_id = create_res.json()["data"]["id"]

    res = await async_client.patch(
        f"/api/v1/addresses/{addr_id}",
        json={"_id": str(ObjectId()), "customerId": str(ObjectId())},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_delete_non_default_address(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Delete a non-default address without affecting default address."""
    res1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Default Home",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 1",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    first_id = res1.json()["data"]["id"]

    res2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Second Address",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 2",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "isDefault": False,
        },
        headers=auth_headers["headers"],
    )
    second_id = res2.json()["data"]["id"]

    del_res = await async_client.delete(f"/api/v1/addresses/{second_id}", headers=auth_headers["headers"])
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deletedAddressId"] == second_id
    assert del_res.json()["data"]["newDefaultAddressId"] is None

    # First remains
    list_res = await async_client.get("/api/v1/addresses", headers=auth_headers["headers"])
    items = list_res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == first_id
    assert items[0]["isDefault"] is True


@pytest.mark.asyncio
async def test_delete_default_address_reassigns_new_default(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Deleting default address reassigns default to the most recently updated remaining address."""
    res1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Original Default",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 1",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    default_id = res1.json()["data"]["id"]

    res2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Remaining Address",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 2",
            "locality": "Index Medical College",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "452016",
            "isDefault": False,
        },
        headers=auth_headers["headers"],
    )
    remaining_id = res2.json()["data"]["id"]

    del_res = await async_client.delete(f"/api/v1/addresses/{default_id}", headers=auth_headers["headers"])
    assert del_res.status_code == 200
    assert del_res.json()["data"]["deletedAddressId"] == default_id
    assert del_res.json()["data"]["newDefaultAddressId"] == remaining_id

    # Verify remaining address is now default
    rem_res = await async_client.get(f"/api/v1/addresses/{remaining_id}", headers=auth_headers["headers"])
    assert rem_res.json()["data"]["isDefault"] is True


@pytest.mark.asyncio
async def test_delete_last_address(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Deleting the last remaining address leaves customer with 0 addresses and newDefaultAddressId is null."""
    res = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Sole Address",
            "recipientName": "Rahul Sharma",
            "recipientMobile": "9876543210",
            "addressLine1": "Plot 1",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
        },
        headers=auth_headers["headers"],
    )
    addr_id = res.json()["data"]["id"]

    del_res = await async_client.delete(f"/api/v1/addresses/{addr_id}", headers=auth_headers["headers"])
    assert del_res.status_code == 200
    assert del_res.json()["data"]["newDefaultAddressId"] is None

    list_res = await async_client.get("/api/v1/addresses", headers=auth_headers["headers"])
    assert list_res.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_set_default_address_endpoint(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Explicitly set an address as default via PATCH /addresses/{id}/default."""
    res1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Addr 1",
            "recipientName": "Rahul",
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
    id1 = res1.json()["data"]["id"]

    res2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Addr 2",
            "recipientName": "Rahul",
            "recipientMobile": "9876543210",
            "addressLine1": "P2",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "isDefault": False,
        },
        headers=auth_headers["headers"],
    )
    id2 = res2.json()["data"]["id"]

    def_res = await async_client.patch(f"/api/v1/addresses/{id2}/default", headers=auth_headers["headers"])
    assert def_res.status_code == 200
    assert def_res.json()["data"]["addressId"] == id2
    assert def_res.json()["data"]["isDefault"] is True

    # Check that addr 1 is not default
    get1 = await async_client.get(f"/api/v1/addresses/{id1}", headers=auth_headers["headers"])
    assert get1.json()["data"]["isDefault"] is False


@pytest.mark.asyncio
async def test_cross_customer_default_and_delete_prevention(async_client: AsyncClient, auth_headers: dict, auth_headers_other: dict):
    """Scenario: Customer 2 cannot set default or delete Customer 1's address."""
    res = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Cust 1 Address",
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
    addr_id = res.json()["data"]["id"]

    # Customer 2 attempts to set default
    patch_other = await async_client.patch(f"/api/v1/addresses/{addr_id}/default", headers=auth_headers_other["headers"])
    assert patch_other.status_code == 404

    # Customer 2 attempts to delete
    del_other = await async_client.delete(f"/api/v1/addresses/{addr_id}", headers=auth_headers_other["headers"])
    assert del_other.status_code == 404


@pytest.mark.asyncio
async def test_invalid_address_id_handling(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Malformed ObjectId returns controlled 404 response."""
    res = await async_client.get("/api/v1/addresses/not-a-valid-object-id", headers=auth_headers["headers"])
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_pincode_and_coordinate_validations(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Validate Indian PIN code and coordinate ranges."""
    # Invalid PIN with letters
    res1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Home",
            "recipientName": "Rahul",
            "recipientMobile": "9876543210",
            "addressLine1": "House 1",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "45311A",
        },
        headers=auth_headers["headers"],
    )
    assert res1.status_code == 422

    # Invalid coordinates (latitude out of range)
    res2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Home",
            "recipientName": "Rahul",
            "recipientMobile": "9876543210",
            "addressLine1": "House 1",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "location": {
                "type": "Point",
                "coordinates": [75.9, 150.0],  # Lat > 90
            },
        },
        headers=auth_headers["headers"],
    )
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_concurrent_default_address_changes(async_client: AsyncClient, auth_headers: dict):
    """Scenario: Concurrent requests to change default address remain consistent with exactly 1 default."""
    res1 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Addr 1",
            "recipientName": "Rahul",
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
    id1 = res1.json()["data"]["id"]

    res2 = await async_client.post(
        "/api/v1/addresses",
        json={
            "label": "Addr 2",
            "recipientName": "Rahul",
            "recipientMobile": "9876543210",
            "addressLine1": "P2",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "isDefault": False,
        },
        headers=auth_headers["headers"],
    )
    id2 = res2.json()["data"]["id"]

    # Send concurrent patches
    await asyncio.gather(
        async_client.patch(f"/api/v1/addresses/{id1}/default", headers=auth_headers["headers"]),
        async_client.patch(f"/api/v1/addresses/{id2}/default", headers=auth_headers["headers"]),
    )

    # Verify exactly one address is default
    list_res = await async_client.get("/api/v1/addresses", headers=auth_headers["headers"])
    defaults = [item for item in list_res.json()["data"]["items"] if item["isDefault"]]
    assert len(defaults) == 1


@pytest.mark.asyncio
async def test_missing_authentication_rejected(async_client: AsyncClient):
    """Scenario: Missing or invalid token returns 401."""
    res = await async_client.get("/api/v1/addresses")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "NOT_AUTHENTICATED"
