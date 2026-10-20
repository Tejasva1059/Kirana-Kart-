from bson import ObjectId
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_categories_and_subcategories(client: AsyncClient, test_db):
    # Insert top-level categories
    cat1_res = await test_db.categories.insert_one({
        "name": "Dairy & Breakfast",
        "slug": "dairy-breakfast",
        "sortOrder": 1,
        "isActive": True,
        "isFeatured": True,
    })
    cat1_id = str(cat1_res.inserted_id)

    cat2_res = await test_db.categories.insert_one({
        "name": "Atta, Rice & Dals",
        "slug": "atta-rice-dals",
        "sortOrder": 2,
        "isActive": True,
        "isFeatured": False,
    })
    cat2_id = str(cat2_res.inserted_id)

    # Inactive category
    await test_db.categories.insert_one({
        "name": "Discontinued Category",
        "slug": "discontinued",
        "sortOrder": 3,
        "isActive": False,
    })

    # Subcategory under cat1
    sub1_res = await test_db.categories.insert_one({
        "name": "Milk & Cream",
        "slug": "milk-cream",
        "parentCategoryId": cat1_id,
        "sortOrder": 1,
        "isActive": True,
    })

    # 1. Test basic list categories (without subcategories)
    res = await client.get("/api/v1/categories")
    assert res.status_code == 200
    body = res.json()
    items = body["data"]["items"]
    assert len(items) == 2
    assert items[0]["name"] == "Dairy & Breakfast"
    assert items[1]["name"] == "Atta, Rice & Dals"
    assert items[0]["subcategories"] is None

    # 2. Test with includeSubcategories=true
    res_sub = await client.get("/api/v1/categories?includeSubcategories=true")
    assert res_sub.status_code == 200
    sub_items = res_sub.json()["data"]["items"]
    assert sub_items[0]["subcategories"] is not None
    assert len(sub_items[0]["subcategories"]) == 1
    assert sub_items[0]["subcategories"][0]["name"] == "Milk & Cream"

    # 3. Test featuredOnly=true
    res_feat = await client.get("/api/v1/categories?featuredOnly=true")
    assert res_feat.status_code == 200
    feat_items = res_feat.json()["data"]["items"]
    assert len(feat_items) == 1
    assert feat_items[0]["name"] == "Dairy & Breakfast"

    # 4. Test GET /categories/{categoryId}
    res_single = await client.get(f"/api/v1/categories/{cat1_id}")
    assert res_single.status_code == 200
    assert res_single.json()["data"]["name"] == "Dairy & Breakfast"

    # 5. Test GET /categories/{categoryId}/subcategories
    res_subs = await client.get(f"/api/v1/categories/{cat1_id}/subcategories")
    assert res_subs.status_code == 200
    subs = res_subs.json()["data"]
    assert len(subs) == 1
    assert subs[0]["name"] == "Milk & Cream"

    # 6. Test 404 on nonexistent category
    non_existent_id = str(ObjectId())
    res_404 = await client.get(f"/api/v1/categories/{non_existent_id}")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "CATEGORY_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_category_products(client: AsyncClient, test_db):
    cat_res = await test_db.categories.insert_one({
        "name": "Beverages",
        "slug": "beverages",
        "isActive": True,
    })
    cat_id = str(cat_res.inserted_id)

    # Insert products
    await test_db.products.insert_one({
        "name": "Green Tea 100g",
        "slug": "green-tea-100g",
        "categoryId": cat_id,
        "isActive": True,
    })
    await test_db.products.insert_one({
        "name": "Black Tea 250g",
        "slug": "black-tea-250g",
        "categoryId": cat_id,
        "isActive": True,
    })

    res = await client.get(f"/api/v1/categories/{cat_id}/products")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["pagination"]["total"] == 2
    assert len(data["items"]) == 2
