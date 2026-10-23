from datetime import datetime, timezone
from bson import ObjectId
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_complete_pulses_category_to_product_flow(client: AsyncClient, test_db):
    """
    Comprehensive verification of the Category-to-Product flow:
    1. Category list (Pulses)
    2. Category details
    3. Category products (Tuar Dal & Chana Dal)
    4. Product details
    5. Product variants (500g, 1kg)
    6. Product availability
    7. Shop inventory
    8. Error handling (nonexistent ID, empty category)
    """
    now = datetime.now(timezone.utc)

    # Setup Shop
    shop_res = await test_db.shops.insert_one({
        "name": "Kirana Kart Khudel Superstore",
        "slug": "kirana-kart-khudel-superstore",
        "serviceAreaIds": ["indore-launch-area"],
        "supportedPostalCodes": ["453115"],
        "timezone": "Asia/Kolkata",
        "isActive": True,
        "acceptsOrders": True,
        "createdAt": now,
        "updatedAt": now,
    })
    shop_id = str(shop_res.inserted_id)

    # Setup Pulses Category
    cat_res = await test_db.categories.insert_one({
        "name": "Pulses",
        "slug": "pulses",
        "description": "High-protein unpolished dals, lentils, and everyday organic pulses",
        "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
        "parentCategoryId": None,
        "sortOrder": 1,
        "isActive": True,
        "isFeatured": True,
        "createdAt": now,
        "updatedAt": now,
    })
    pulses_id = str(cat_res.inserted_id)

    # Empty Category (for empty category test)
    empty_cat_res = await test_db.categories.insert_one({
        "name": "Empty Test Category",
        "slug": "empty-category",
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    })
    empty_cat_id = str(empty_cat_res.inserted_id)

    # Setup Products under Pulses: Tuar Dal & Chana Dal
    tuar_res = await test_db.products.insert_one({
        "name": "Tata Sampann Unpolished Tuar Dal",
        "slug": "tuar-dal",
        "brand": "Tata Sampann",
        "categoryId": pulses_id,
        "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
        "images": ["https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500"],
        "searchKeywords": ["tuar", "arhar", "dal", "pulses"],
        "isActive": True,
        "isFeatured": True,
        "createdAt": now,
        "updatedAt": now,
    })
    tuar_id = str(tuar_res.inserted_id)

    chana_res = await test_db.products.insert_one({
        "name": "Tata Sampann Unpolished Chana Dal",
        "slug": "chana-dal",
        "brand": "Tata Sampann",
        "categoryId": pulses_id,
        "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
        "images": ["https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500"],
        "searchKeywords": ["chana", "dal", "pulses"],
        "isActive": True,
        "isFeatured": True,
        "createdAt": now,
        "updatedAt": now,
    })
    chana_id = str(chana_res.inserted_id)

    # Inactive Product under Pulses
    await test_db.products.insert_one({
        "name": "Discontinued Moong Dal",
        "slug": "discontinued-moong",
        "categoryId": pulses_id,
        "isActive": False,
        "createdAt": now,
        "updatedAt": now,
    })

    # Setup Variants for Tuar Dal (500g and 1kg)
    v_tuar_500g = await test_db.product_variants.insert_one({
        "productId": tuar_id,
        "sku": "TUAR-DAL-500G",
        "variantName": "500 g",
        "packSize": 0.5,
        "unit": "kg",
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    })
    v_tuar_500g_id = str(v_tuar_500g.inserted_id)

    v_tuar_1kg = await test_db.product_variants.insert_one({
        "productId": tuar_id,
        "sku": "TUAR-DAL-1KG",
        "variantName": "1 kg",
        "packSize": 1.0,
        "unit": "kg",
        "isActive": True,
        "createdAt": now,
        "updatedAt": now,
    })
    v_tuar_1kg_id = str(v_tuar_1kg.inserted_id)

    # Setup Inventory for Tuar Dal
    await test_db.shop_inventory.insert_many([
        {
            "shopId": shop_id,
            "productId": tuar_id,
            "variantId": v_tuar_500g_id,
            "pricePaise": 8500,  # ₹85.00
            "mrpPaise": 9500,  # ₹95.00
            "stockQuantity": 30,
            "reservedQuantity": 0,
            "isAvailable": True,
            "updatedAt": now,
        },
        {
            "shopId": shop_id,
            "productId": tuar_id,
            "variantId": v_tuar_1kg_id,
            "pricePaise": 16500,  # ₹165.00
            "mrpPaise": 18500,  # ₹185.00
            "stockQuantity": 25,
            "reservedQuantity": 0,
            "isAvailable": True,
            "updatedAt": now,
        },
    ])

    # -------------------------------------------------------------
    # Test A — Fetch categories: GET /api/v1/categories
    # -------------------------------------------------------------
    res_cats = await client.get("/api/v1/categories")
    assert res_cats.status_code == 200
    cats_data = res_cats.json()
    assert cats_data["success"] is True
    pulses_item = next((c for c in cats_data["data"]["items"] if c["name"] == "Pulses"), None)
    assert pulses_item is not None
    assert pulses_item["id"] == pulses_id
    assert pulses_item["slug"] == "pulses"

    # -------------------------------------------------------------
    # Test B — Fetch Pulses details: GET /api/v1/categories/{categoryId}
    # -------------------------------------------------------------
    res_cat_detail = await client.get(f"/api/v1/categories/{pulses_id}")
    assert res_cat_detail.status_code == 200
    cat_detail = res_cat_detail.json()["data"]
    assert cat_detail["name"] == "Pulses"
    assert cat_detail["id"] == pulses_id

    # -------------------------------------------------------------
    # Test C — Fetch Pulses products: GET /api/v1/categories/{categoryId}/products
    # -------------------------------------------------------------
    res_cat_prods = await client.get(f"/api/v1/categories/{pulses_id}/products?shopId={shop_id}")
    assert res_cat_prods.status_code == 200
    prods_data = res_cat_prods.json()["data"]
    prod_names = [p["name"] for p in prods_data["items"]]
    assert "Tata Sampann Unpolished Tuar Dal" in prod_names
    assert "Tata Sampann Unpolished Chana Dal" in prod_names
    # Inactive product excluded
    assert "Discontinued Moong Dal" not in prod_names

    # -------------------------------------------------------------
    # Test D — Fetch product details: GET /api/v1/products/{productId}
    # -------------------------------------------------------------
    res_prod = await client.get(f"/api/v1/products/{tuar_id}?shopId={shop_id}")
    assert res_prod.status_code == 200
    prod_detail = res_prod.json()["data"]
    assert prod_detail["id"] == tuar_id
    assert prod_detail["name"] == "Tata Sampann Unpolished Tuar Dal"
    assert prod_detail["brand"] == "Tata Sampann"
    assert prod_detail["price"]["amountPaise"] == 8500  # min variant price (500g)
    assert prod_detail["availability"]["isAvailable"] is True
    assert prod_detail["availability"]["availableQuantity"] == 55  # 30 + 25

    # -------------------------------------------------------------
    # Test E — Fetch product variants: GET /api/v1/products/{productId}/variants
    # -------------------------------------------------------------
    res_vars = await client.get(f"/api/v1/products/{tuar_id}/variants?shopId={shop_id}")
    assert res_vars.status_code == 200
    variants = res_vars.json()["data"]["items"]
    assert len(variants) == 2
    var_500 = next(v for v in variants if v["variantName"] == "500 g")
    var_1kg = next(v for v in variants if v["variantName"] == "1 kg")
    assert var_500["pricePaise"] == 8500
    assert var_500["availableQuantity"] == 30
    assert var_1kg["pricePaise"] == 16500
    assert var_1kg["availableQuantity"] == 25

    # -------------------------------------------------------------
    # Test F — Check product availability: GET /api/v1/products/{productId}/availability
    # -------------------------------------------------------------
    res_avail = await client.get(f"/api/v1/products/{tuar_id}/availability?shopId={shop_id}&variantId={v_tuar_500g_id}")
    assert res_avail.status_code == 200
    avail_info = res_avail.json()["data"]
    assert avail_info["isAvailable"] is True
    assert avail_info["availableQuantity"] == 30
    assert avail_info["pricePaise"] == 8500
    assert avail_info["reasonCode"] == "AVAILABLE"

    # -------------------------------------------------------------
    # Test G — Shop catalogue: GET /api/v1/shops/{shopId}/products
    # -------------------------------------------------------------
    res_shop_cat = await client.get(f"/api/v1/shops/{shop_id}/products")
    assert res_shop_cat.status_code == 200
    shop_prods = res_shop_cat.json()["data"]["items"]
    assert len(shop_prods) >= 1
    tuar_in_shop = next((p for p in shop_prods if p["id"] == tuar_id), None)
    assert tuar_in_shop is not None
    assert tuar_in_shop["price"]["amountPaise"] == 8500

    # -------------------------------------------------------------
    # Test H — Empty category returns valid empty list, not error
    # -------------------------------------------------------------
    res_empty = await client.get(f"/api/v1/categories/{empty_cat_id}/products")
    assert res_empty.status_code == 200
    assert res_empty.json()["data"]["items"] == []
    assert res_empty.json()["data"]["pagination"]["total"] == 0

    # -------------------------------------------------------------
    # Test I — Nonexistent category returns 404
    # -------------------------------------------------------------
    non_existent = str(ObjectId())
    res_404 = await client.get(f"/api/v1/categories/{non_existent}/products")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "CATEGORY_NOT_FOUND"
