from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_banners_active_only(client: AsyncClient, test_db):
    now = datetime.now(timezone.utc)
    # Insert active banner
    await test_db.banners.insert_one({
        "title": "Fresh Vegetables Sale",
        "subtitle": "Up to 30% off",
        "imageUrl": "https://cdn.example.com/banners/veg.webp",
        "targetType": "category",
        "position": 1,
        "isActive": True,
        "startsAt": now - timedelta(days=1),
        "endsAt": now + timedelta(days=1),
    })
    # Insert inactive banner
    await test_db.banners.insert_one({
        "title": "Old Inactive Promo",
        "imageUrl": "https://cdn.example.com/banners/old.webp",
        "targetType": "none",
        "position": 2,
        "isActive": False,
    })
    # Insert expired banner
    await test_db.banners.insert_one({
        "title": "Expired Promo",
        "imageUrl": "https://cdn.example.com/banners/expired.webp",
        "targetType": "none",
        "position": 3,
        "isActive": True,
        "endsAt": now - timedelta(hours=1),
    })

    res = await client.get("/api/v1/banners")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    items = body["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Fresh Vegetables Sale"


@pytest.mark.asyncio
async def test_get_banners_service_area_filter(client: AsyncClient, test_db):
    now = datetime.now(timezone.utc)
    await test_db.banners.insert_one({
        "title": "Indore Launch Special",
        "imageUrl": "https://cdn.example.com/banners/indore.webp",
        "targetType": "none",
        "position": 1,
        "isActive": True,
        "serviceAreaIds": ["indore-launch-area"],
    })
    await test_db.banners.insert_one({
        "title": "Bhopal Special",
        "imageUrl": "https://cdn.example.com/banners/bhopal.webp",
        "targetType": "none",
        "position": 2,
        "isActive": True,
        "serviceAreaIds": ["bhopal-area"],
    })

    res = await client.get("/api/v1/banners?serviceAreaId=indore-launch-area")
    assert res.status_code == 200
    items = res.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Indore Launch Special"
