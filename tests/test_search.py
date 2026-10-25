from datetime import datetime, timezone
from bson import ObjectId
import pytest
from httpx import AsyncClient


@pytest.fixture
async def setup_search_catalog(test_db):
    """Seed sample categories, shops, products, variants, and inventory for search tests."""
    now = datetime.now(timezone.utc)

    # 1. Categories
    cat_pulses = await test_db.categories.insert_one({
        "name": "Pulses",
        "slug": "pulses",
        "isActive": True,
        "isFeatured": True,
        "sortOrder": 1,
        "createdAt": now,
        "updatedAt": now,
    })
    pulses_id = str(cat_pulses.inserted_id)

    cat_dairy = await test_db.categories.insert_one({
        "name": "Dairy & Breakfast",
        "slug": "dairy-breakfast",
        "isActive": True,
        "isFeatured": False,
        "sortOrder": 2,
        "createdAt": now,
        "updatedAt": now,
    })
    dairy_id = str(cat_dairy.inserted_id)

    # 2. Shop
    shop_res = await test_db.shops.insert_one({
        "name": "Kirana Kart Khudel Superstore",
        "slug": "kirana-kart-khudel",
        "isActive": True,
        "acceptsOrders": True,
        "timezone": "Asia/Kolkata",
        "createdAt": now,
        "updatedAt": now,
    })
    shop_id = str(shop_res.inserted_id)

    # 3. Products
    p_tuar = await test_db.products.insert_one({
        "name": "Tata Sampann Unpolished Tuar Dal",
        "slug": "tata-tuar-dal",
        "brand": "Tata Sampann",
        "categoryId": pulses_id,
        "searchKeywords": ["toor", "arhar", "dal", "protein"],
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    })
    tuar_id = str(p_tuar.inserted_id)

    p_chana = await test_db.products.insert_one({
        "name": "Fortune Unpolished Chana Dal",
        "slug": "fortune-chana-dal",
        "brand": "Fortune",
        "categoryId": pulses_id,
        "searchKeywords": ["chana", "dal", "bengal gram"],
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    })
    chana_id = str(p_chana.inserted_id)

    p_milk = await test_db.products.insert_one({
        "name": "Amul Taaza Toned Milk 1L",
        "slug": "amul-taaza-milk",
        "brand": "Amul",
        "categoryId": dairy_id,
        "searchKeywords": ["milk", "doodh", "dairy"],
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    })
    milk_id = str(p_milk.inserted_id)

    # Inactive product: should never appear in search results
    await test_db.products.insert_one({
        "name": "Expired Tuar Dal",
        "slug": "expired-tuar",
        "brand": "Old Brand",
        "categoryId": pulses_id,
        "isActive": False,
        "createdAt": now,
        "updatedAt": now,
    })

    # Out-of-stock product
    p_paneer = await test_db.products.insert_one({
        "name": "Amul Malai Paneer 200g",
        "slug": "amul-paneer",
        "brand": "Amul",
        "categoryId": dairy_id,
        "searchKeywords": ["paneer", "dairy", "cheese"],
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    })
    paneer_id = str(p_paneer.inserted_id)

    # 4. Variants
    v_tuar = await test_db.product_variants.insert_one({
        "productId": tuar_id,
        "sku": "TATA-TUAR-1KG",
        "variantName": "1 kg",
        "packSize": 1.0,
        "unit": "kg",
        "isActive": True,
    })
    v_tuar_id = str(v_tuar.inserted_id)

    v_chana = await test_db.product_variants.insert_one({
        "productId": chana_id,
        "sku": "FORTUNE-CHANA-1KG",
        "variantName": "1 kg",
        "packSize": 1.0,
        "unit": "kg",
        "isActive": True,
    })
    v_chana_id = str(v_chana.inserted_id)

    v_milk = await test_db.product_variants.insert_one({
        "productId": milk_id,
        "sku": "AMUL-MILK-1L",
        "variantName": "1 Litre",
        "packSize": 1.0,
        "unit": "l",
        "isActive": True,
    })
    v_milk_id = str(v_milk.inserted_id)

    v_paneer = await test_db.product_variants.insert_one({
        "productId": paneer_id,
        "sku": "AMUL-PANEER-200G",
        "variantName": "200 g",
        "packSize": 200.0,
        "unit": "g",
        "isActive": True,
    })
    v_paneer_id = str(v_paneer.inserted_id)

    # 5. Inventory
    await test_db.shop_inventory.insert_many([
        {
            "shopId": shop_id,
            "productId": tuar_id,
            "variantId": v_tuar_id,
            "pricePaise": 16500,  # ₹165.00
            "mrpPaise": 18500,
            "stockQuantity": 20,
            "reservedQuantity": 0,
            "isAvailable": True,
        },
        {
            "shopId": shop_id,
            "productId": chana_id,
            "variantId": v_chana_id,
            "pricePaise": 10500,  # ₹105.00
            "mrpPaise": 12000,
            "stockQuantity": 15,
            "reservedQuantity": 0,
            "isAvailable": True,
        },
        {
            "shopId": shop_id,
            "productId": milk_id,
            "variantId": v_milk_id,
            "pricePaise": 5600,  # ₹56.00
            "mrpPaise": 5600,
            "stockQuantity": 30,
            "reservedQuantity": 0,
            "isAvailable": True,
        },
        {
            "shopId": shop_id,
            "productId": paneer_id,
            "variantId": v_paneer_id,
            "pricePaise": 9000,  # ₹90.00
            "mrpPaise": 9500,
            "stockQuantity": 0,  # Out of stock
            "reservedQuantity": 0,
            "isAvailable": True,
        },
    ])

    return {
        "pulses_id": pulses_id,
        "dairy_id": dairy_id,
        "shop_id": shop_id,
        "tuar_id": tuar_id,
        "chana_id": chana_id,
        "milk_id": milk_id,
        "paneer_id": paneer_id,
    }


# ==============================================================================
# Scenario 1 & 2: Search for existing product & partial product name
# ==============================================================================
@pytest.mark.asyncio
async def test_search_existing_and_partial_product(client: AsyncClient, setup_search_catalog):
    # 1. Full product name
    res = await client.get("/api/v1/search?q=Tata%20Sampann%20Unpolished%20Tuar%20Dal")
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data["items"]) >= 1
    assert data["items"][0]["name"] == "Tata Sampann Unpolished Tuar Dal"
    assert data["items"][0]["category"]["name"] == "Pulses"

    # 2. Partial product name "tuar"
    res_partial = await client.get("/api/v1/search?q=tuar")
    assert res_partial.status_code == 200
    items = res_partial.json()["data"]["items"]
    assert any("Tuar" in item["name"] for item in items)


# ==============================================================================
# Scenario 3: Case-insensitive search
# ==============================================================================
@pytest.mark.asyncio
async def test_search_case_insensitive(client: AsyncClient, setup_search_catalog):
    res_upper = await client.get("/api/v1/search?q=TUAR%20DAL")
    assert res_upper.status_code == 200
    items_upper = res_upper.json()["data"]["items"]
    assert len(items_upper) >= 1

    res_mixed = await client.get("/api/v1/search?q=tUaR%20dAl")
    assert res_mixed.status_code == 200
    items_mixed = res_mixed.json()["data"]["items"]
    assert len(items_mixed) >= 1
    assert items_upper[0]["id"] == items_mixed[0]["id"]


# ==============================================================================
# Scenario 4: Empty and too-short search terms
# ==============================================================================
@pytest.mark.asyncio
async def test_search_empty_and_short_queries(client: AsyncClient):
    # 1. Blank q
    res_blank = await client.get("/api/v1/search?q=")
    assert res_blank.status_code == 400
    assert res_blank.json()["error"]["code"] == "EMPTY_SEARCH_QUERY"

    # 2. Whitespace only
    res_spaces = await client.get("/api/v1/search?q=%20%20%20")
    assert res_spaces.status_code == 400
    assert res_spaces.json()["error"]["code"] == "EMPTY_SEARCH_QUERY"

    # 3. Autocomplete with < 2 chars returns empty suggestions without error
    res_auto = await client.get("/api/v1/search/suggestions?q=t")
    assert res_auto.status_code == 200
    assert res_auto.json()["data"]["suggestions"] == []


# ==============================================================================
# Scenario 5: No matching products
# ==============================================================================
@pytest.mark.asyncio
async def test_search_no_matching_products(client: AsyncClient, setup_search_catalog):
    res = await client.get("/api/v1/search?q=NonexistentExoticProduct123")
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["items"] == []
    assert body["pagination"]["total"] == 0


# ==============================================================================
# Scenario 6: Autocomplete suggestions limits & types
# ==============================================================================
@pytest.mark.asyncio
async def test_autocomplete_suggestions(client: AsyncClient, setup_search_catalog):
    res = await client.get("/api/v1/search/suggestions?q=tu&limit=5")
    assert res.status_code == 200
    suggestions = res.json()["data"]["suggestions"]
    assert len(suggestions) <= 5
    assert len(suggestions) > 0
    assert any("Tuar" in s["text"] for s in suggestions)
    assert suggestions[0]["type"] in ["product", "category", "brand"]


# ==============================================================================
# Scenario 7 & 8: Trending searches with and without analytics data
# ==============================================================================
@pytest.mark.asyncio
async def test_trending_searches_flow(client: AsyncClient, test_db, setup_search_catalog):
    # Clean DB: without search events, trending returns empty list
    await test_db.search_events.delete_many({})
    res_empty = await client.get("/api/v1/search/trending")
    assert res_empty.status_code == 200
    assert res_empty.json()["data"] == []

    # Execute searches to record events
    await client.get("/api/v1/search?q=chana%20dal")
    await client.get("/api/v1/search?q=tuar%20dal")

    # Manually insert additional distinct event to verify count aggregation
    now = datetime.now(timezone.utc)
    await test_db.search_events.insert_many([
        {"query": "Tuar Dal", "normalizedQuery": "tuar dal", "resultCount": 2, "createdAt": now},
        {"query": "tuar dal", "normalizedQuery": "tuar dal", "resultCount": 2, "createdAt": now},
    ])

    res_trending = await client.get("/api/v1/search/trending")
    assert res_trending.status_code == 200
    trending = res_trending.json()["data"]
    assert len(trending) >= 1
    # Tuar dal should have highest count
    top = trending[0]
    assert "tuar dal" in top["query"].lower()
    assert top["searchCount"] >= 2


# ==============================================================================
# Scenario 9: Filtering products by category
# ==============================================================================
@pytest.mark.asyncio
async def test_filter_products_by_category(client: AsyncClient, setup_search_catalog):
    catalog = setup_search_catalog
    pulses_id = catalog["pulses_id"]

    res = await client.get(f"/api/v1/products?categoryId={pulses_id}")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 2  # Tuar Dal and Chana Dal
    assert all(item["categoryId"] == pulses_id for item in items)


# ==============================================================================
# Scenario 10: Filtering by an invalid / malformed category ID
# ==============================================================================
@pytest.mark.asyncio
async def test_filter_products_invalid_category_id(client: AsyncClient):
    # Malformed categoryId raises 400 Bad Request
    res = await client.get("/api/v1/products?categoryId=invalid!id@format")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_CATEGORY_ID"


# ==============================================================================
# Scenario 11: Sorting by ascending price
# ==============================================================================
@pytest.mark.asyncio
async def test_sort_products_price_asc(client: AsyncClient, setup_search_catalog):
    catalog = setup_search_catalog
    shop_id = catalog["shop_id"]

    res = await client.get(f"/api/v1/products?shopId={shop_id}&sortBy=price_asc")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    prices = [item["price"]["amountPaise"] for item in items if item["price"]]
    assert prices == sorted(prices)
    # Milk is 5600, Chana Dal is 10500, Tuar Dal is 16500
    assert prices[0] == 5600


# ==============================================================================
# Scenario 12: Sorting by descending price
# ==============================================================================
@pytest.mark.asyncio
async def test_sort_products_price_desc(client: AsyncClient, setup_search_catalog):
    catalog = setup_search_catalog
    shop_id = catalog["shop_id"]

    res = await client.get(f"/api/v1/products?shopId={shop_id}&sortBy=price_desc")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    prices = [item["price"]["amountPaise"] for item in items if item["price"]]
    assert prices == sorted(prices, reverse=True)
    assert prices[0] == 16500


# ==============================================================================
# Scenario 13: Filtering in-stock products
# ==============================================================================
@pytest.mark.asyncio
async def test_filter_in_stock_products(client: AsyncClient, setup_search_catalog):
    catalog = setup_search_catalog
    shop_id = catalog["shop_id"]

    res = await client.get(f"/api/v1/products?shopId={shop_id}&inStock=true")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    # Paneer is stock=0, so it must NOT be included
    names = [i["name"] for i in items]
    assert "Amul Malai Paneer 200g" not in names
    assert all(i["availability"]["isAvailable"] is True for i in items)


# ==============================================================================
# Scenario 14: Filtering out-of-stock products
# ==============================================================================
@pytest.mark.asyncio
async def test_filter_out_of_stock_products(client: AsyncClient, setup_search_catalog):
    catalog = setup_search_catalog
    shop_id = catalog["shop_id"]

    res = await client.get(f"/api/v1/products?shopId={shop_id}&inStock=false")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    names = [i["name"] for i in items]
    assert "Amul Malai Paneer 200g" in names
    assert all(i["availability"]["isAvailable"] is False for i in items)


# ==============================================================================
# Scenario 15 & 16: Combined filters & accurate pagination metadata
# ==============================================================================
@pytest.mark.asyncio
async def test_combined_filters_and_pagination(client: AsyncClient, setup_search_catalog):
    catalog = setup_search_catalog
    pulses_id = catalog["pulses_id"]
    shop_id = catalog["shop_id"]

    # Category=Pulses + inStock=true + sortBy=price_asc + page=1 + limit=1
    res = await client.get(
        f"/api/v1/products?categoryId={pulses_id}&shopId={shop_id}&inStock=true&sortBy=price_asc&page=1&limit=1"
    )
    assert res.status_code == 200
    body = res.json()["data"]
    assert len(body["items"]) == 1
    # Lowest price pulse is Chana Dal (₹105.00)
    assert body["items"][0]["name"] == "Fortune Unpolished Chana Dal"

    pagination = body["pagination"]
    assert pagination["total"] == 2
    assert pagination["page"] == 1
    assert pagination["limit"] == 1
    assert pagination["totalPages"] == 2
    assert pagination["hasMore"] is True

    # Page 2
    res_p2 = await client.get(
        f"/api/v1/products?categoryId={pulses_id}&shopId={shop_id}&inStock=true&sortBy=price_asc&page=2&limit=1"
    )
    assert res_p2.status_code == 200
    body_p2 = res_p2.json()["data"]
    assert len(body_p2["items"]) == 1
    assert body_p2["items"][0]["name"] == "Tata Sampann Unpolished Tuar Dal"
    assert body_p2["pagination"]["page"] == 2
    assert body_p2["pagination"]["hasMore"] is False


# ==============================================================================
# Scenario 17: Shop-specific pricing in search
# ==============================================================================
@pytest.mark.asyncio
async def test_search_shop_specific_pricing(client: AsyncClient, setup_search_catalog):
    catalog = setup_search_catalog
    shop_id = catalog["shop_id"]

    res = await client.get(f"/api/v1/search?q=tuar&shopId={shop_id}")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["price"]["amountPaise"] == 16500
    assert items[0]["inStock"] is True


# ==============================================================================
# Scenario 18: Inactive products excluded from search
# ==============================================================================
@pytest.mark.asyncio
async def test_inactive_products_excluded(client: AsyncClient, setup_search_catalog):
    res = await client.get("/api/v1/search?q=expired")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 0


# ==============================================================================
# Scenario 19: Invalid query parameters validation
# ==============================================================================
@pytest.mark.asyncio
async def test_invalid_query_parameters(client: AsyncClient):
    # 1. Negative minPrice
    res_neg = await client.get("/api/v1/search?q=tea&minPrice=-100")
    assert res_neg.status_code == 400
    assert res_neg.json()["error"]["code"] == "INVALID_PRICE"

    # 2. minPrice > maxPrice
    res_range = await client.get("/api/v1/search?q=tea&minPrice=5000&maxPrice=1000")
    assert res_range.status_code == 400
    assert res_range.json()["error"]["code"] == "INVALID_PRICE_RANGE"

    # 3. Unsupported sortBy value
    res_sort = await client.get("/api/v1/search?q=tea&sortBy=unsupported_sort")
    assert res_sort.status_code == 400
    assert res_sort.json()["error"]["code"] == "UNSUPPORTED_SORT"

    # 4. Limit out of range
    res_limit = await client.get("/api/v1/search?q=tea&limit=100")
    assert res_limit.status_code == 400
    assert res_limit.json()["error"]["code"] == "INVALID_LIMIT"


# ==============================================================================
# Scenario 20: Stable ordering for equal prices
# ==============================================================================
@pytest.mark.asyncio
async def test_stable_ordering_equal_prices(client: AsyncClient, test_db):
    now = datetime.now(timezone.utc)
    # Insert 3 products with identical prices
    p1 = await test_db.products.insert_one({"name": "Brand A Biscuit", "slug": "biscuit-a", "isActive": True, "createdAt": now})
    p2 = await test_db.products.insert_one({"name": "Brand B Biscuit", "slug": "biscuit-b", "isActive": True, "createdAt": now})
    p3 = await test_db.products.insert_one({"name": "Brand C Biscuit", "slug": "biscuit-c", "isActive": True, "createdAt": now})

    res = await client.get("/api/v1/products?q=Biscuit&sortBy=name_asc")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    names = [i["name"] for i in items]
    assert names == ["Brand A Biscuit", "Brand B Biscuit", "Brand C Biscuit"]
