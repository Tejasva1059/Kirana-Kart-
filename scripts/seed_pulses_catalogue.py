"""
Optional development-only seed script for Pulses, Tuar Dal, and Chana Dal.
Prepares sample data for manual verification and testing without altering live production records.
Run with: python scripts/seed_pulses_catalogue.py
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from bson import ObjectId

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.logging import logger
from app.db.mongodb import get_db, mongo_manager


async def seed_pulses_data():
    print("Connecting to MongoDB...")
    await mongo_manager.connect()
    db = get_db()
    now = datetime.now(timezone.utc)

    # 1. Check or insert 'Pulses' category
    existing_cat = await db.categories.find_one({"slug": "pulses"})
    if existing_cat:
        pulses_id = existing_cat["_id"]
        print(f"[FOUND] Category 'Pulses' already exists with ID: {pulses_id}")
    else:
        pulses_id = ObjectId()
        await db.categories.insert_one({
            "_id": pulses_id,
            "name": "Pulses",
            "slug": "pulses",
            "description": "High-protein unpolished dals, lentils, and everyday organic pulses",
            "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
            "parentCategoryId": None,
            "sortOrder": 5,
            "isActive": True,
            "isFeatured": True,
            "createdAt": now,
            "updatedAt": now,
        })
        print(f"[CREATED] Category 'Pulses' created with ID: {pulses_id}")

    # 2. Find active shop
    shop = await db.shops.find_one({"isActive": True})
    if not shop:
        shop_id = ObjectId()
        await db.shops.insert_one({
            "_id": shop_id,
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
        print(f"[CREATED] Default shop created with ID: {shop_id}")
    else:
        shop_id = shop["_id"]
        print(f"[FOUND] Using active shop: '{shop.get('name')}' (ID: {shop_id})")

    # 3. Check or insert Tuar Dal
    tuar_prod = await db.products.find_one({"slug": "tuar-dal"})
    if not tuar_prod:
        tuar_id = ObjectId()
        await db.products.insert_one({
            "_id": tuar_id,
            "name": "Tata Sampann Unpolished Tuar Dal",
            "slug": "tuar-dal",
            "shortDescription": "Rich in protein, unpolished arhar dal",
            "description": "Tata Sampann unpolished Tuar Dal undergoes a 5-step purity process for natural goodness.",
            "brand": "Tata Sampann",
            "categoryId": pulses_id,
            "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
            "images": ["https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500"],
            "searchKeywords": ["tuar", "arhar", "dal", "pulses", "toor"],
            "isActive": True,
            "isFeatured": True,
            "createdAt": now,
            "updatedAt": now,
        })

        v_tuar_500g = ObjectId()
        v_tuar_1kg = ObjectId()
        await db.product_variants.insert_many([
            {
                "_id": v_tuar_500g,
                "productId": tuar_id,
                "sku": "TUAR-DAL-500G",
                "variantName": "500 g",
                "packSize": 0.5,
                "unit": "kg",
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": v_tuar_1kg,
                "productId": tuar_id,
                "sku": "TUAR-DAL-1KG",
                "variantName": "1 kg",
                "packSize": 1.0,
                "unit": "kg",
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
            },
        ])

        await db.shop_inventory.insert_many([
            {
                "shopId": shop_id,
                "productId": tuar_id,
                "variantId": v_tuar_500g,
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
                "variantId": v_tuar_1kg,
                "pricePaise": 16500,  # ₹165.00
                "mrpPaise": 18500,  # ₹185.00
                "stockQuantity": 25,
                "reservedQuantity": 0,
                "isAvailable": True,
                "updatedAt": now,
            },
        ])
        print(f"[CREATED] 'Tuar Dal' inserted with ID: {tuar_id} (500g: ₹85, 1kg: ₹165)")
    else:
        print(f"[FOUND] 'Tuar Dal' already exists with ID: {tuar_prod['_id']}")

    # 4. Check or insert Chana Dal
    chana_prod = await db.products.find_one({"slug": "chana-dal"})
    if not chana_prod:
        chana_id = ObjectId()
        await db.products.insert_one({
            "_id": chana_id,
            "name": "Tata Sampann Unpolished Chana Dal",
            "slug": "chana-dal",
            "shortDescription": "Pure Bengal gram dal",
            "description": "Premium unpolished chana dal sourced directly from farmers, wholesome and authentic.",
            "brand": "Tata Sampann",
            "categoryId": pulses_id,
            "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
            "images": ["https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500"],
            "searchKeywords": ["chana", "dal", "pulses", "bengal gram"],
            "isActive": True,
            "isFeatured": True,
            "createdAt": now,
            "updatedAt": now,
        })

        v_chana_500g = ObjectId()
        v_chana_1kg = ObjectId()
        await db.product_variants.insert_many([
            {
                "_id": v_chana_500g,
                "productId": chana_id,
                "sku": "CHANA-DAL-500G",
                "variantName": "500 g",
                "packSize": 0.5,
                "unit": "kg",
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": v_chana_1kg,
                "productId": chana_id,
                "sku": "CHANA-DAL-1KG",
                "variantName": "1 kg",
                "packSize": 1.0,
                "unit": "kg",
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
            },
        ])

        await db.shop_inventory.insert_many([
            {
                "shopId": shop_id,
                "productId": chana_id,
                "variantId": v_chana_500g,
                "pricePaise": 6500,  # ₹65.00
                "mrpPaise": 7500,  # ₹75.00
                "stockQuantity": 40,
                "reservedQuantity": 0,
                "isAvailable": True,
                "updatedAt": now,
            },
            {
                "shopId": shop_id,
                "productId": chana_id,
                "variantId": v_chana_1kg,
                "pricePaise": 12500,  # ₹125.00
                "mrpPaise": 14500,  # ₹145.00
                "stockQuantity": 20,
                "reservedQuantity": 0,
                "isAvailable": True,
                "updatedAt": now,
            },
        ])
        print(f"[CREATED] 'Chana Dal' inserted with ID: {chana_id} (500g: ₹65, 1kg: ₹125)")
    else:
        print(f"[FOUND] 'Chana Dal' already exists with ID: {chana_prod['_id']}")

    print("\n[SUCCESS] Pulses catalogue seeding completed successfully!")
    await mongo_manager.close()


if __name__ == "__main__":
    asyncio.run(seed_pulses_data())
