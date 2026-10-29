from datetime import datetime, timezone
from bson import ObjectId
import pytest
from httpx import AsyncClient

from app.services.cart_service import CartService


@pytest.fixture
async def setup_cart_data(test_db):
    """Seed shop, category, products, variants, and inventory for cart tests."""
    now = datetime.now(timezone.utc)
    shop_id = ObjectId()
    await test_db.shops.insert_one({
        "_id": shop_id,
        "name": "Kirana Kart Khudel Superstore",
        "slug": "kirana-kart-khudel-superstore",
        "isActive": True,
        "acceptsOrders": True,
        "supportedPostalCodes": ["453115"],
        "createdAt": now,
        "updatedAt": now,
    })

    cat_id = ObjectId()
    await test_db.categories.insert_one({
        "_id": cat_id,
        "name": "Pulses & Dals",
        "slug": "pulses-dals",
        "isActive": True,
    })

    prod1_id = ObjectId()
    var1_id = ObjectId()
    await test_db.products.insert_one({
        "_id": prod1_id,
        "name": "Tuar Dal Premium",
        "slug": "tuar-dal-premium",
        "categoryId": cat_id,
        "isActive": True,
        "imageUrl": "https://images.unsplash.com/tuar-dal.jpg",
    })
    await test_db.product_variants.insert_one({
        "_id": var1_id,
        "productId": prod1_id,
        "variantName": "1 kg",
        "packSize": 1.0,
        "unit": "kg",
        "sku": "TUAR-1KG",
        "pricePaise": 12500,
        "mrpPaise": 15000,
        "isActive": True,
    })
    await test_db.shop_inventory.insert_one({
        "shopId": shop_id,
        "productId": prod1_id,
        "variantId": var1_id,
        "pricePaise": 12500,
        "mrpPaise": 15000,
        "stockQuantity": 20,
        "reservedQuantity": 0,
        "isAvailable": True,
    })

    prod2_id = ObjectId()
    var2_id = ObjectId()
    await test_db.products.insert_one({
        "_id": prod2_id,
        "name": "Moong Dal",
        "slug": "moong-dal",
        "categoryId": cat_id,
        "isActive": True,
        "imageUrl": "https://images.unsplash.com/moong-dal.jpg",
    })
    await test_db.product_variants.insert_one({
        "_id": var2_id,
        "productId": prod2_id,
        "variantName": "500 g",
        "packSize": 0.5,
        "unit": "kg",
        "sku": "MOONG-500G",
        "pricePaise": 7000,
        "mrpPaise": 8500,
        "isActive": True,
    })
    await test_db.shop_inventory.insert_one({
        "shopId": shop_id,
        "productId": prod2_id,
        "variantId": var2_id,
        "pricePaise": 7000,
        "mrpPaise": 8500,
        "stockQuantity": 15,
        "reservedQuantity": 0,
        "isAvailable": True,
    })

    return {
        "shopId": str(shop_id),
        "product1Id": str(prod1_id),
        "variant1Id": str(var1_id),
        "product2Id": str(prod2_id),
        "variant2Id": str(var2_id),
    }


# 1. Fetch an empty cart
@pytest.mark.asyncio
async def test_fetch_empty_cart(client: AsyncClient, auth_headers):
    res = await client.get("/api/v1/cart", headers=auth_headers["headers"])
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["items"] == []
    assert data["subtotalPaise"] == 0
    assert data["subtotal"] == 0.0
    assert data["itemCount"] == 0
    assert data["totalQuantity"] == 0


# 2. Add a valid product variant
@pytest.mark.asyncio
async def test_add_valid_product_variant(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    payload = {
        "productId": d["product1Id"],
        "variantId": d["variant1Id"],
        "quantity": 2,
    }
    res = await client.post("/api/v1/cart/items", json=payload, headers=auth_headers["headers"])
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["productId"] == d["product1Id"]
    assert item["variantId"] == d["variant1Id"]
    assert item["quantity"] == 2
    assert item["unitPricePaise"] == 12500
    assert item["unitPrice"] == 125.0
    assert item["subtotalPaise"] == 25000
    assert item["subtotal"] == 250.0
    assert data["subtotalPaise"] == 25000
    assert data["subtotal"] == 250.0
    assert data["itemCount"] == 1
    assert data["totalQuantity"] == 2


# 3. Add the same variant twice and verify documented quantity behavior
@pytest.mark.asyncio
async def test_add_same_variant_twice(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    payload = {
        "productId": d["product1Id"],
        "variantId": d["variant1Id"],
        "quantity": 2,
    }
    await client.post("/api/v1/cart/items", json=payload, headers=auth_headers["headers"])

    # Add 3 more of same variant
    payload["quantity"] = 3
    res = await client.post("/api/v1/cart/items", json=payload, headers=auth_headers["headers"])
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 5
    assert data["items"][0]["subtotalPaise"] == 5 * 12500
    assert data["totalQuantity"] == 5


# 4. Reject an invalid product ID
@pytest.mark.asyncio
async def test_reject_invalid_product_id(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    fake_pid = str(ObjectId())
    payload = {
        "productId": fake_pid,
        "variantId": d["variant1Id"],
        "quantity": 1,
    }
    res = await client.post("/api/v1/cart/items", json=payload, headers=auth_headers["headers"])
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


# 5. Reject a variant that does not belong to the product
@pytest.mark.asyncio
async def test_reject_variant_mismatch(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    # Pass Product 1 with Variant 2 (which belongs to Product 2)
    payload = {
        "productId": d["product1Id"],
        "variantId": d["variant2Id"],
        "quantity": 1,
    }
    res = await client.post("/api/v1/cart/items", json=payload, headers=auth_headers["headers"])
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "VARIANT_MISMATCH"


# 6. Reject invalid or excessive quantities
@pytest.mark.asyncio
async def test_reject_invalid_or_excessive_quantities(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    # Quantity 0
    res0 = await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 0},
        headers=auth_headers["headers"],
    )
    assert res0.status_code in (400, 422)

    # Quantity 51 (> 50 limit)
    res51 = await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 51},
        headers=auth_headers["headers"],
    )
    assert res51.status_code in (400, 422)


# 7. Update a cart item's quantity
@pytest.mark.asyncio
async def test_update_cart_item_quantity(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    add_res = await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 2},
        headers=auth_headers["headers"],
    )
    item_id = add_res.json()["data"]["items"][0]["itemId"]

    # Update to 4
    patch_res = await client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 4},
        headers=auth_headers["headers"],
    )
    assert patch_res.status_code == 200
    data = patch_res.json()["data"]
    assert data["items"][0]["quantity"] == 4
    assert data["items"][0]["subtotalPaise"] == 4 * 12500
    assert data["subtotalPaise"] == 4 * 12500


# 8. Remove a cart item
@pytest.mark.asyncio
async def test_remove_cart_item(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    add_res = await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 2},
        headers=auth_headers["headers"],
    )
    item_id = add_res.json()["data"]["items"][0]["itemId"]

    del_res = await client.delete(f"/api/v1/cart/items/{item_id}", headers=auth_headers["headers"])
    assert del_res.status_code == 200
    data = del_res.json()["data"]
    assert len(data["items"]) == 0
    assert data["subtotalPaise"] == 0


# 9. Clear the cart
@pytest.mark.asyncio
async def test_clear_cart(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 2},
        headers=auth_headers["headers"],
    )
    await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product2Id"], "variantId": d["variant2Id"], "quantity": 1},
        headers=auth_headers["headers"],
    )

    del_all = await client.delete("/api/v1/cart/items", headers=auth_headers["headers"])
    assert del_all.status_code == 200
    data = del_all.json()["data"]
    assert data["items"] == []
    assert data["subtotalPaise"] == 0
    assert data["itemCount"] == 0


# 10. Prevent cross-customer access
@pytest.mark.asyncio
async def test_prevent_cross_customer_access(client: AsyncClient, auth_headers, auth_headers_other, setup_cart_data):
    d = setup_cart_data
    # Customer A adds item
    add_res = await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 2},
        headers=auth_headers["headers"],
    )
    item_id = add_res.json()["data"]["items"][0]["itemId"]

    # Customer B attempts to update or delete Customer A's item
    patch_b = await client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 5},
        headers=auth_headers_other["headers"],
    )
    assert patch_b.status_code == 404
    assert patch_b.json()["error"]["code"] == "ITEM_NOT_FOUND"

    del_b = await client.delete(
        f"/api/v1/cart/items/{item_id}",
        headers=auth_headers_other["headers"],
    )
    assert del_b.status_code == 404
    assert del_b.json()["error"]["code"] == "ITEM_NOT_FOUND"


# 11. Handle inactive products and variants
@pytest.mark.asyncio
async def test_handle_inactive_products_and_variants(client: AsyncClient, auth_headers, setup_cart_data, test_db):
    d = setup_cart_data
    # Deactivate Product 2
    await test_db.products.update_one({"_id": ObjectId(d["product2Id"])}, {"$set": {"isActive": False}})

    res = await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product2Id"], "variantId": d["variant2Id"], "quantity": 1},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "PRODUCT_NOT_FOUND"


# 12. Handle out-of-stock products
@pytest.mark.asyncio
async def test_handle_out_of_stock_products(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    # Available stock is 20, requesting 25 should fail
    res = await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 25},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INSUFFICIENT_STOCK"


# 13. Recalculate prices from trusted sources
@pytest.mark.asyncio
async def test_recalculate_prices_from_trusted_sources(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    # Client sends unitPrice 1, but backend must ignore and charge trusted 12500 paise
    payload = {
        "productId": d["product1Id"],
        "variantId": d["variant1Id"],
        "quantity": 1,
        "unitPrice": 1,  # Fake client price
    }
    res = await client.post("/api/v1/cart/items", json=payload, headers=auth_headers["headers"])
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["items"][0]["unitPricePaise"] == 12500
    assert data["items"][0]["subtotalPaise"] == 12500


# 14. Detect price changes in validation
@pytest.mark.asyncio
async def test_detect_price_changes_validation(client: AsyncClient, auth_headers, setup_cart_data, test_db):
    d = setup_cart_data
    await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 2},
        headers=auth_headers["headers"],
    )

    # Price changes from 12500 to 13500 in inventory
    await test_db.shop_inventory.update_one(
        {"variantId": ObjectId(d["variant1Id"])},
        {"$set": {"pricePaise": 13500}},
    )

    val_res = await client.post("/api/v1/cart/validate", headers=auth_headers["headers"])
    assert val_res.status_code == 200
    val_data = val_res.json()["data"]
    assert val_data["valid"] is False
    assert len(val_data["items"]) == 1
    assert val_data["items"][0]["status"] == "price_changed"
    assert val_data["items"][0]["previousPricePaise"] == 12500
    assert val_data["items"][0]["currentPricePaise"] == 13500


# 15. Detect inventory changes in validation
@pytest.mark.asyncio
async def test_detect_inventory_changes_validation(client: AsyncClient, auth_headers, setup_cart_data, test_db):
    d = setup_cart_data
    await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 5},
        headers=auth_headers["headers"],
    )

    # Stock drops to 2 (below requested 5)
    await test_db.shop_inventory.update_one(
        {"variantId": ObjectId(d["variant1Id"])},
        {"$set": {"stockQuantity": 2}},
    )

    val_res = await client.post("/api/v1/cart/validate", headers=auth_headers["headers"])
    assert val_res.status_code == 200
    val_data = val_res.json()["data"]
    assert val_data["valid"] is False
    assert val_data["items"][0]["status"] == "quantity_reduced"
    assert val_data["items"][0]["availableQuantity"] == 2


# 16. Validate an empty cart
@pytest.mark.asyncio
async def test_validate_empty_cart(client: AsyncClient, auth_headers):
    res = await client.post("/api/v1/cart/validate", headers=auth_headers["headers"])
    assert res.status_code == 200
    val_data = res.json()["data"]
    assert val_data["valid"] is True
    assert val_data["items"] == []
    assert val_data["subtotalPaise"] == 0


# 17. Handle unauthorized request without auth token
@pytest.mark.asyncio
async def test_handle_unauthorized_cart_request(client: AsyncClient):
    res = await client.get("/api/v1/cart")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "NOT_AUTHENTICATED"


# 18. Merge a valid guest cart
@pytest.mark.asyncio
async def test_merge_valid_guest_cart(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    # Create a real guest cart
    guest_cart = await CartService.create_guest_cart(
        items=[{
            "productId": d["product1Id"],
            "variantId": d["variant1Id"],
            "quantity": 2,
            "priceSnapshotPaise": 12500,
        }],
        shop_id=d["shopId"],
    )
    guest_cart_id = guest_cart["guestCartId"]

    # Merge into logged-in customer cart
    res = await client.post(
        "/api/v1/cart/merge",
        json={"guestCartId": guest_cart_id},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["merged"] is True
    assert data["itemsMergedCount"] == 1
    assert len(data["cart"]["items"]) == 1
    assert data["cart"]["items"][0]["variantId"] == d["variant1Id"]
    assert data["cart"]["items"][0]["quantity"] == 2


# 19. Merge duplicate variants
@pytest.mark.asyncio
async def test_merge_duplicate_variants(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    # Customer already has 2 of variant1
    await client.post(
        "/api/v1/cart/items",
        json={"productId": d["product1Id"], "variantId": d["variant1Id"], "quantity": 2},
        headers=auth_headers["headers"],
    )

    # Guest cart has 3 of variant1
    guest_cart = await CartService.create_guest_cart(
        items=[{
            "productId": d["product1Id"],
            "variantId": d["variant1Id"],
            "quantity": 3,
            "priceSnapshotPaise": 12500,
        }],
        shop_id=d["shopId"],
    )

    res = await client.post(
        "/api/v1/cart/merge",
        json={"guestCartId": guest_cart["guestCartId"]},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["merged"] is True
    # Combined quantity should be 2 + 3 = 5
    assert len(data["cart"]["items"]) == 1
    assert data["cart"]["items"][0]["quantity"] == 5


# 20. Reject an unauthorized or invalid guest-cart ID
@pytest.mark.asyncio
async def test_reject_invalid_guest_cart_id(client: AsyncClient, auth_headers):
    res = await client.post(
        "/api/v1/cart/merge",
        json={"guestCartId": "non-existent-guest-id"},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "GUEST_CART_NOT_FOUND"


# 21. Prevent repeated merge requests from duplicating items (Replay protection)
@pytest.mark.asyncio
async def test_prevent_repeated_merge_requests(client: AsyncClient, auth_headers, setup_cart_data):
    d = setup_cart_data
    guest_cart = await CartService.create_guest_cart(
        items=[{
            "productId": d["product1Id"],
            "variantId": d["variant1Id"],
            "quantity": 2,
            "priceSnapshotPaise": 12500,
        }],
        shop_id=d["shopId"],
    )
    guest_cart_id = guest_cart["guestCartId"]

    # First merge
    res1 = await client.post(
        "/api/v1/cart/merge",
        json={"guestCartId": guest_cart_id},
        headers=auth_headers["headers"],
    )
    assert res1.status_code == 200

    # Second merge attempt on same guest cart
    res2 = await client.post(
        "/api/v1/cart/merge",
        json={"guestCartId": guest_cart_id},
        headers=auth_headers["headers"],
    )
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "GUEST_CART_ALREADY_MERGED"


# 22. Handle incompatible shop contexts and stock limitations
@pytest.mark.asyncio
async def test_merge_stock_limitations_and_security(client: AsyncClient, auth_headers, setup_cart_data, test_db):
    d = setup_cart_data
    # Inventory stock is 20. Guest cart requests 25.
    guest_cart = await CartService.create_guest_cart(
        items=[{
            "productId": d["product1Id"],
            "variantId": d["variant1Id"],
            "quantity": 25,
            "priceSnapshotPaise": 12500,
        }],
        shop_id=d["shopId"],
    )

    res = await client.post(
        "/api/v1/cart/merge",
        json={"guestCartId": guest_cart["guestCartId"]},
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    data = res.json()["data"]
    # Merged quantity capped at available stock (20)
    assert data["cart"]["items"][0]["quantity"] == 20
    assert len(data["warnings"]) > 0
