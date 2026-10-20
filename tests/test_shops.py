from bson import ObjectId
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_shops_and_service_area_filtering(client: AsyncClient, test_db):
    # Active Shop 1 in Indore Launch Area
    s1 = await test_db.shops.insert_one({
        "name": "Kirana Kart Khudel Store",
        "slug": "kirana-kart-khudel-store",
        "serviceAreaIds": ["indore-launch-area"],
        "supportedPostalCodes": ["453115"],
        "isActive": True,
        "acceptsOrders": True,
    })
    s1_id = str(s1.inserted_id)

    # Active Shop 2 in Bhopal
    s2 = await test_db.shops.insert_one({
        "name": "Kirana Kart Bhopal Store",
        "slug": "kirana-kart-bhopal-store",
        "serviceAreaIds": ["bhopal-area"],
        "supportedPostalCodes": ["462001"],
        "isActive": True,
        "acceptsOrders": False,
    })

    # Inactive Shop
    await test_db.shops.insert_one({
        "name": "Closed Permanently Store",
        "slug": "closed-store",
        "isActive": False,
    })

    # 1. List all active shops
    res = await client.get("/api/v1/shops")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 2

    # 2. Filter by serviceAreaId
    res_area = await client.get("/api/v1/shops?serviceAreaId=indore-launch-area")
    assert res_area.status_code == 200
    items_area = res_area.json()["data"]["items"]
    assert len(items_area) == 1
    assert items_area[0]["id"] == s1_id

    # 3. Filter by postalCode
    res_pin = await client.get("/api/v1/shops?postalCode=453115")
    assert res_pin.status_code == 200
    assert len(res_pin.json()["data"]["items"]) == 1

    # 4. Filter by acceptsOrders=true
    res_orders = await client.get("/api/v1/shops?acceptsOrders=true")
    assert res_orders.status_code == 200
    assert len(res_orders.json()["data"]["items"]) == 1
    assert res_orders.json()["data"]["items"][0]["id"] == s1_id


@pytest.mark.asyncio
async def test_get_shop_details_and_availability(client: AsyncClient, test_db):
    shop = await test_db.shops.insert_one({
        "name": "Kirana Kart Express",
        "slug": "kirana-kart-express",
        "description": "Quick grocery delivery in 15 mins",
        "serviceAreaIds": ["indore-launch-area"],
        "isActive": True,
        "acceptsOrders": True,
        "timezone": "Asia/Kolkata",
    })
    shop_id = str(shop.inserted_id)

    # 1. GET /shops/{shopId}
    res_details = await client.get(f"/api/v1/shops/{shop_id}")
    assert res_details.status_code == 200
    data = res_details.json()["data"]
    assert data["name"] == "Kirana Kart Express"
    assert data["isOpen"] is True
    assert data["acceptsOrders"] is True

    # 2. GET /shops/{shopId}/availability
    res_avail = await client.get(f"/api/v1/shops/{shop_id}/availability?serviceAreaId=indore-launch-area")
    assert res_avail.status_code == 200
    avail_data = res_avail.json()["data"]
    assert avail_data["isOrderable"] is True
    assert avail_data["reasonCode"] == "AVAILABLE"

    # 3. Test unserviceable serviceAreaId
    res_unserv = await client.get(f"/api/v1/shops/{shop_id}/availability?serviceAreaId=other-unsupported-area")
    assert res_unserv.status_code == 200
    assert res_unserv.json()["data"]["isOrderable"] is False
    assert res_unserv.json()["data"]["reasonCode"] == "SHOP_NOT_SERVICEABLE"

    # 4. Test 404 for nonexistent shop
    non_existent = str(ObjectId())
    res_404 = await client.get(f"/api/v1/shops/{non_existent}")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "SHOP_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_shop_catalogue(client: AsyncClient, test_db):
    # Setup Shop
    shop = await test_db.shops.insert_one({
        "name": "Local Kirana Store",
        "slug": "local-kirana-store",
        "isActive": True,
        "acceptsOrders": True,
    })
    shop_id = str(shop.inserted_id)

    # Setup Product & Variant
    prod = await test_db.products.insert_one({
        "name": "Fortune Atta 5kg",
        "slug": "fortune-atta-5kg",
        "isActive": True,
    })
    prod_id = str(prod.inserted_id)

    var = await test_db.product_variants.insert_one({
        "productId": prod_id,
        "sku": "FORTUNE-5KG",
        "variantName": "5 kg",
        "packSize": 5.0,
        "unit": "kg",
        "isActive": True,
    })
    var_id = str(var.inserted_id)

    # Inventory
    await test_db.shop_inventory.insert_one({
        "shopId": shop_id,
        "productId": prod_id,
        "variantId": var_id,
        "pricePaise": 22000,
        "mrpPaise": 25000,
        "stockQuantity": 20,
        "reservedQuantity": 0,
        "isAvailable": True,
    })

    res = await client.get(f"/api/v1/shops/{shop_id}/products")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["name"] == "Fortune Atta 5kg"
    assert items[0]["price"]["amountPaise"] == 22000
    assert items[0]["availability"]["availableQuantity"] == 20
