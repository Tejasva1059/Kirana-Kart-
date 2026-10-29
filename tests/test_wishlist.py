from datetime import datetime, timezone
from bson import ObjectId
import pytest
from httpx import AsyncClient


@pytest.fixture
async def setup_wishlist_data(test_db):
    """Seed category, products, and variants for wishlist tests."""
    now = datetime.now(timezone.utc)
    cat_id = ObjectId()
    await test_db.categories.insert_one({
        "_id": cat_id,
        "name": "Dairy & Breakfast",
        "slug": "dairy-breakfast",
        "isActive": True,
    })

    prod1_id = ObjectId()
    await test_db.products.insert_one({
        "_id": prod1_id,
        "name": "Amul Butter 500g",
        "slug": "amul-butter-500g",
        "brand": "Amul",
        "categoryId": cat_id,
        "isActive": True,
        "imageUrl": "https://images.unsplash.com/butter.jpg",
        "createdAt": now,
        "updatedAt": now,
    })
    await test_db.product_variants.insert_one({
        "_id": ObjectId(),
        "productId": prod1_id,
        "variantName": "500g Pack",
        "packSize": 0.5,
        "unit": "kg",
        "sku": "AMUL-BUTTER-500",
        "pricePaise": 27500,
        "mrpPaise": 28500,
        "isActive": True,
    })

    prod2_id = ObjectId()
    await test_db.products.insert_one({
        "_id": prod2_id,
        "name": "Mother Dairy Milk 1L",
        "slug": "mother-dairy-milk-1l",
        "brand": "Mother Dairy",
        "categoryId": cat_id,
        "isActive": True,
        "imageUrl": "https://images.unsplash.com/milk.jpg",
        "createdAt": now,
        "updatedAt": now,
    })

    return {
        "product1Id": str(prod1_id),
        "product2Id": str(prod2_id),
    }


# 23. Fetch an empty wishlist
@pytest.mark.asyncio
async def test_fetch_empty_wishlist(client: AsyncClient, auth_headers):
    res = await client.get("/api/v1/wishlist", headers=auth_headers["headers"])
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["items"] == []
    assert data["totalCount"] == 0


# 24. Add a valid product
@pytest.mark.asyncio
async def test_add_valid_wishlist_product(client: AsyncClient, auth_headers, setup_wishlist_data):
    d = setup_wishlist_data
    res = await client.post(
        "/api/v1/wishlist/items",
        json={"productId": d["product1Id"]},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    item = res.json()["data"]
    assert item["productId"] == d["product1Id"]
    assert item["productName"] == "Amul Butter 500g"
    assert item["pricePaise"] == 27500
    assert item["price"] == 275.0

    # Verify wishlist fetch shows the item
    fetch_res = await client.get("/api/v1/wishlist", headers=auth_headers["headers"])
    assert fetch_res.status_code == 200
    w_data = fetch_res.json()["data"]
    assert w_data["totalCount"] == 1
    assert w_data["items"][0]["productId"] == d["product1Id"]


# 25. Add a duplicate product (idempotent addition)
@pytest.mark.asyncio
async def test_add_duplicate_wishlist_product(client: AsyncClient, auth_headers, setup_wishlist_data):
    d = setup_wishlist_data
    # First addition
    res1 = await client.post(
        "/api/v1/wishlist/items",
        json={"productId": d["product1Id"]},
        headers=auth_headers["headers"],
    )
    assert res1.status_code == 200

    # Second addition of same product
    res2 = await client.post(
        "/api/v1/wishlist/items",
        json={"productId": d["product1Id"]},
        headers=auth_headers["headers"],
    )
    assert res2.status_code == 200

    # Total items should remain 1
    fetch_res = await client.get("/api/v1/wishlist", headers=auth_headers["headers"])
    assert fetch_res.status_code == 200
    assert fetch_res.json()["data"]["totalCount"] == 1


# 26. Remove a wishlist item
@pytest.mark.asyncio
async def test_remove_wishlist_item(client: AsyncClient, auth_headers, setup_wishlist_data):
    d = setup_wishlist_data
    # Add product 1 and product 2
    await client.post(
        "/api/v1/wishlist/items",
        json={"productId": d["product1Id"]},
        headers=auth_headers["headers"],
    )
    await client.post(
        "/api/v1/wishlist/items",
        json={"productId": d["product2Id"]},
        headers=auth_headers["headers"],
    )

    # Remove product 1
    del_res = await client.delete(
        f"/api/v1/wishlist/items/{d['product1Id']}",
        headers=auth_headers["headers"],
    )
    assert del_res.status_code == 200

    # Verify only product 2 remains
    fetch_res = await client.get("/api/v1/wishlist", headers=auth_headers["headers"])
    assert fetch_res.status_code == 200
    items = fetch_res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["productId"] == d["product2Id"]


# 27. Keep an unavailable product in the wishlist
@pytest.mark.asyncio
async def test_keep_unavailable_product_in_wishlist(client: AsyncClient, auth_headers, setup_wishlist_data, test_db):
    d = setup_wishlist_data
    # Add product 1
    await client.post(
        "/api/v1/wishlist/items",
        json={"productId": d["product1Id"]},
        headers=auth_headers["headers"],
    )

    # Deactivate product in database
    await test_db.products.update_one({"_id": ObjectId(d["product1Id"])}, {"$set": {"isActive": False}})

    # Product remains in wishlist with isAvailable=False
    fetch_res = await client.get("/api/v1/wishlist", headers=auth_headers["headers"])
    assert fetch_res.status_code == 200
    items = fetch_res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["productId"] == d["product1Id"]
    assert items[0]["isAvailable"] is False


# 28. Prevent cross-customer access to wishlist
@pytest.mark.asyncio
async def test_prevent_cross_customer_wishlist_access(client: AsyncClient, auth_headers, auth_headers_other, setup_wishlist_data):
    d = setup_wishlist_data
    # Customer A adds product 1
    await client.post(
        "/api/v1/wishlist/items",
        json={"productId": d["product1Id"]},
        headers=auth_headers["headers"],
    )

    # Customer B fetches wishlist -> must be empty
    fetch_b = await client.get("/api/v1/wishlist", headers=auth_headers_other["headers"])
    assert fetch_b.status_code == 200
    assert fetch_b.json()["data"]["items"] == []
    assert fetch_b.json()["data"]["totalCount"] == 0

    # Customer B tries to remove product 1 -> does not affect Customer A's wishlist
    await client.delete(
        f"/api/v1/wishlist/items/{d['product1Id']}",
        headers=auth_headers_other["headers"],
    )

    fetch_a = await client.get("/api/v1/wishlist", headers=auth_headers["headers"])
    assert fetch_a.status_code == 200
    assert len(fetch_a.json()["data"]["items"]) == 1


# 29. Handle invalid product IDs
@pytest.mark.asyncio
async def test_handle_invalid_product_id(client: AsyncClient, auth_headers):
    fake_pid = str(ObjectId())
    res = await client.post(
        "/api/v1/wishlist/items",
        json={"productId": fake_pid},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"
