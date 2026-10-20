from bson import ObjectId
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_products_filtering_and_pagination(client: AsyncClient, test_db):
    cat_res = await test_db.categories.insert_one({"name": "Groceries", "slug": "groceries", "isActive": True})
    cat_id = str(cat_res.inserted_id)

    p1 = await test_db.products.insert_one({
        "name": "Tata Tea Gold 500g",
        "slug": "tata-tea-gold-500g",
        "brand": "Tata",
        "categoryId": cat_id,
        "searchKeywords": ["chai", "tea"],
        "isActive": True,
        "isFeatured": True,
    })
    p2 = await test_db.products.insert_one({
        "name": "Red Label Tea 250g",
        "slug": "red-label-tea-250g",
        "brand": "Brooke Bond",
        "categoryId": cat_id,
        "searchKeywords": ["chai", "tea"],
        "isActive": True,
        "isFeatured": False,
    })
    # Inactive product
    await test_db.products.insert_one({
        "name": "Expired Coffee",
        "slug": "expired-coffee",
        "categoryId": cat_id,
        "isActive": False,
    })

    # 1. Search by q=Tata
    res_q = await client.get("/api/v1/products?q=Tata")
    assert res_q.status_code == 200
    items_q = res_q.json()["data"]["items"]
    assert len(items_q) == 1
    assert items_q[0]["name"] == "Tata Tea Gold 500g"

    # 2. Search by brand
    res_brand = await client.get("/api/v1/products?brand=Tata")
    assert res_brand.status_code == 200
    assert len(res_brand.json()["data"]["items"]) == 1

    # 3. Filter featuredOnly=true
    res_feat = await client.get("/api/v1/products?featuredOnly=true")
    assert res_feat.status_code == 200
    assert len(res_feat.json()["data"]["items"]) == 1

    # 4. Pagination limit=1
    res_page = await client.get("/api/v1/products?limit=1&offset=0")
    assert res_page.status_code == 200
    pag = res_page.json()["data"]["pagination"]
    assert pag["total"] == 2
    assert pag["limit"] == 1
    assert pag["hasMore"] is True


@pytest.mark.asyncio
async def test_product_shop_pricing_and_inventory(client: AsyncClient, test_db):
    cat_res = await test_db.categories.insert_one({"name": "Rice", "slug": "rice", "isActive": True})
    cat_id = str(cat_res.inserted_id)

    # Insert Shop
    shop_res = await test_db.shops.insert_one({
        "name": "Kirana Kart Khudel Superstore",
        "slug": "kirana-kart-khudel",
        "isActive": True,
        "acceptsOrders": True,
        "timezone": "Asia/Kolkata",
    })
    shop_id = str(shop_res.inserted_id)

    # Insert Product
    prod_res = await test_db.products.insert_one({
        "name": "Basmati Rice",
        "slug": "basmati-rice",
        "categoryId": cat_id,
        "isActive": True,
    })
    prod_id = str(prod_res.inserted_id)

    # Insert Variants
    v1_res = await test_db.product_variants.insert_one({
        "productId": prod_id,
        "sku": "BASMATI-1KG",
        "variantName": "1 kg",
        "packSize": 1.0,
        "unit": "kg",
        "isActive": True,
    })
    v1_id = str(v1_res.inserted_id)

    # Insert Inventory for Shop
    await test_db.shop_inventory.insert_one({
        "shopId": shop_id,
        "productId": prod_id,
        "variantId": v1_id,
        "pricePaise": 9500,
        "mrpPaise": 11000,
        "stockQuantity": 15,
        "reservedQuantity": 3,  # Available: 12
        "isAvailable": True,
    })

    # 1. Without shop context: price and availability must NOT be fabricated
    res_no_shop = await client.get(f"/api/v1/products/{prod_id}")
    assert res_no_shop.status_code == 200
    data_no_shop = res_no_shop.json()["data"]
    assert data_no_shop["price"] is None
    assert data_no_shop["availability"] is None

    # 2. With shop context: price and availability are shop-scoped
    res_with_shop = await client.get(f"/api/v1/products/{prod_id}?shopId={shop_id}")
    assert res_with_shop.status_code == 200
    data_with_shop = res_with_shop.json()["data"]
    assert data_with_shop["price"]["amountPaise"] == 9500
    assert data_with_shop["price"]["currency"] == "INR"
    assert data_with_shop["availability"]["isAvailable"] is True
    assert data_with_shop["availability"]["availableQuantity"] == 12

    # 3. GET /products/{productId}/variants with shop context
    res_var = await client.get(f"/api/v1/products/{prod_id}/variants?shopId={shop_id}")
    assert res_var.status_code == 200
    vars_list = res_var.json()["data"]["items"]
    assert len(vars_list) == 1
    assert vars_list[0]["pricePaise"] == 9500
    assert vars_list[0]["availableQuantity"] == 12

    # 4. GET /products/{productId}/availability
    res_avail = await client.get(f"/api/v1/products/{prod_id}/availability?shopId={shop_id}&variantId={v1_id}")
    assert res_avail.status_code == 200
    avail_body = res_avail.json()["data"]
    assert avail_body["isAvailable"] is True
    assert avail_body["availableQuantity"] == 12
    assert avail_body["reasonCode"] == "AVAILABLE"


@pytest.mark.asyncio
async def test_product_availability_shop_closed_or_out_of_stock(client: AsyncClient, test_db):
    cat_res = await test_db.categories.insert_one({"name": "Snacks", "slug": "snacks", "isActive": True})
    cat_id = str(cat_res.inserted_id)

    # Closed Shop
    shop_res = await test_db.shops.insert_one({
        "name": "Night Shop",
        "slug": "night-shop",
        "isActive": True,
        "acceptsOrders": False,  # Not accepting orders
    })
    shop_id = str(shop_res.inserted_id)

    prod_res = await test_db.products.insert_one({
        "name": "Potato Chips",
        "slug": "potato-chips",
        "categoryId": cat_id,
        "isActive": True,
    })
    prod_id = str(prod_res.inserted_id)

    v_res = await test_db.product_variants.insert_one({
        "productId": prod_id,
        "sku": "CHIPS-50G",
        "variantName": "50 g",
        "packSize": 50.0,
        "unit": "g",
        "isActive": True,
    })
    v_id = str(v_res.inserted_id)

    # 1. Check availability with shop not accepting orders
    res = await client.get(f"/api/v1/products/{prod_id}/availability?shopId={shop_id}&variantId={v_id}")
    assert res.status_code == 200
    assert res.json()["data"]["isAvailable"] is False
    assert res.json()["data"]["reasonCode"] == "SHOP_NOT_ACCEPTING_ORDERS"


@pytest.mark.asyncio
async def test_related_products(client: AsyncClient, test_db):
    cat_res = await test_db.categories.insert_one({"name": "Oils", "slug": "oils", "isActive": True})
    cat_id = str(cat_res.inserted_id)

    p1 = await test_db.products.insert_one({"name": "Mustard Oil 1L", "slug": "mustard-oil", "categoryId": cat_id, "isActive": True})
    p1_id = str(p1.inserted_id)

    p2 = await test_db.products.insert_one({"name": "Sunflower Oil 1L", "slug": "sunflower-oil", "categoryId": cat_id, "isActive": True})
    p2_id = str(p2.inserted_id)

    res = await client.get(f"/api/v1/products/{p1_id}/related")
    assert res.status_code == 200
    items = res.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == p2_id
    assert items[0]["id"] != p1_id  # Original product excluded
