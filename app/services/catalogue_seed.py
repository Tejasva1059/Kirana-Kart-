from datetime import datetime, timezone
from bson import ObjectId
from app.core.logging import logger
from app.db.mongodb import get_db


async def seed_default_catalogue_if_needed() -> None:
    """Seed initial categories, shops, products, and banners if collections are empty or missing Pulses."""
    db = get_db()
    cat_count = await db.categories.count_documents({})
    now = datetime.now(timezone.utc)

    if cat_count == 0:
        logger.info("Seeding initial Kirana Kart catalogue data...")

        # 1. Categories
        cat1_id = ObjectId()
        cat2_id = ObjectId()
        cat3_id = ObjectId()
        cat4_id = ObjectId()

        categories = [
            {
                "_id": cat1_id,
                "name": "Dairy & Breakfast",
                "slug": "dairy-breakfast",
                "description": "Fresh milk, curd, paneer, and breakfast essentials",
                "imageUrl": "https://images.unsplash.com/photo-1528750997573-59b89d56f4f7?w=500",
                "parentCategoryId": None,
                "sortOrder": 1,
                "isActive": True,
                "isFeatured": True,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": ObjectId(),
                "name": "Milk & Cream",
                "slug": "milk-cream",
                "description": "Farm-fresh pouch and tetra pack milk",
                "parentCategoryId": cat1_id,
                "sortOrder": 1,
                "isActive": True,
                "isFeatured": False,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": cat2_id,
                "name": "Atta, Rice & Dals",
                "slug": "atta-rice-dals",
                "description": "Flours, premium grains, and organic pulses",
                "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
                "parentCategoryId": None,
                "sortOrder": 2,
                "isActive": True,
                "isFeatured": True,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": cat3_id,
                "name": "Fresh Vegetables",
                "slug": "fresh-vegetables",
                "description": "Daily harvested farm fresh vegetables",
                "imageUrl": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=500",
                "parentCategoryId": None,
                "sortOrder": 3,
                "isActive": True,
                "isFeatured": True,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": cat4_id,
                "name": "Snacks & Drinks",
                "slug": "snacks-drinks",
                "description": "Chips, namkeen, cold beverages, and tea",
                "imageUrl": "https://images.unsplash.com/photo-1563729784474-d77dbb933a9e?w=500",
                "parentCategoryId": None,
                "sortOrder": 4,
                "isActive": True,
                "isFeatured": False,
                "createdAt": now,
                "updatedAt": now,
            },
        ]
        await db.categories.insert_many(categories)

        # 2. Shop
        shop_id = ObjectId()
        shop = {
            "_id": shop_id,
            "name": "Kirana Kart Khudel Superstore",
            "slug": "kirana-kart-khudel-superstore",
            "description": "Main quick-delivery hub serving Khudel, Index Medical College, and surrounding corridor",
            "logoUrl": "https://images.unsplash.com/photo-1578916171728-46686eac8d58?w=300",
            "contactPhone": "9876543210",
            "serviceAreaIds": ["indore-launch-area"],
            "supportedPostalCodes": ["453115", "452016", "455223"],
            "timezone": "Asia/Kolkata",
            "isActive": True,
            "acceptsOrders": True,
            "openingHours": {
                "monday": {"openTime": "06:00", "closeTime": "23:00", "isOpen": True},
                "tuesday": {"openTime": "06:00", "closeTime": "23:00", "isOpen": True},
                "wednesday": {"openTime": "06:00", "closeTime": "23:00", "isOpen": True},
                "thursday": {"openTime": "06:00", "closeTime": "23:00", "isOpen": True},
                "friday": {"openTime": "06:00", "closeTime": "23:00", "isOpen": True},
                "saturday": {"openTime": "06:00", "closeTime": "23:00", "isOpen": True},
                "sunday": {"openTime": "06:00", "closeTime": "23:00", "isOpen": True},
            },
            "createdAt": now,
            "updatedAt": now,
        }
        await db.shops.insert_one(shop)

        # 3. Banner
        banner = {
            "title": "Zero Delivery Charges!",
            "subtitle": "Order fresh essentials in 15 mins across Khudel & Index Medical College",
            "imageUrl": "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=1000",
            "targetType": "category",
            "targetId": str(cat2_id),
            "position": 1,
            "isActive": True,
            "serviceAreaIds": ["indore-launch-area"],
            "createdAt": now,
            "updatedAt": now,
        }
        await db.banners.insert_one(banner)

        # 4. Products & Variants & Inventory
        prod1_id = ObjectId()
        var1_id = ObjectId()
        prod2_id = ObjectId()
        var2_id = ObjectId()

        products = [
            {
                "_id": prod1_id,
                "name": "Fortune Sharbati Atta 5kg",
                "slug": "fortune-sharbati-atta-5kg",
                "shortDescription": "100% whole wheat flour",
                "description": "Made from premium MP Sharbati wheat grains, high fibre and soft rotis.",
                "brand": "Fortune",
                "categoryId": cat2_id,
                "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
                "images": ["https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500"],
                "searchKeywords": ["atta", "flour", "wheat", "gehu", "roti", "fortune"],
                "isActive": True,
                "isFeatured": True,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": prod2_id,
                "name": "Amul Taaza Homogenised Toned Milk 1L",
                "slug": "amul-taaza-toned-milk-1l",
                "shortDescription": "Pasteurised toned milk",
                "description": "Fresh and pure toned milk from Amul, rich in calcium and protein.",
                "brand": "Amul",
                "categoryId": cat1_id,
                "imageUrl": "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=500",
                "images": ["https://images.unsplash.com/photo-1550583724-b2692b85b150?w=500"],
                "searchKeywords": ["milk", "amul", "doodh", "dairy"],
                "isActive": True,
                "isFeatured": True,
                "createdAt": now,
                "updatedAt": now,
            },
        ]
        await db.products.insert_many(products)

        variants = [
            {
                "_id": var1_id,
                "productId": prod1_id,
                "sku": "FORTUNE-ATTA-5KG",
                "variantName": "5 kg",
                "packSize": 5.0,
                "unit": "kg",
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
            },
            {
                "_id": var2_id,
                "productId": prod2_id,
                "sku": "AMUL-TAAZA-1L",
                "variantName": "1 Litre",
                "packSize": 1.0,
                "unit": "l",
                "isActive": True,
                "createdAt": now,
                "updatedAt": now,
            },
        ]
        await db.product_variants.insert_many(variants)

        inventories = [
            {
                "shopId": shop_id,
                "productId": prod1_id,
                "variantId": var1_id,
                "pricePaise": 24500,  # ₹245.00
                "mrpPaise": 27500,  # ₹275.00
                "stockQuantity": 40,
                "reservedQuantity": 0,
                "isAvailable": True,
                "updatedAt": now,
            },
            {
                "shopId": shop_id,
                "productId": prod2_id,
                "variantId": var2_id,
                "pricePaise": 5600,  # ₹56.00
                "mrpPaise": 5600,  # ₹56.00
                "stockQuantity": 25,
                "reservedQuantity": 0,
                "isAvailable": True,
                "updatedAt": now,
            },
        ]
        await db.shop_inventory.insert_many(inventories)
        logger.info("Successfully seeded launch catalogue data (Categories, Shop, Banner, Products, Inventory).")

    # 5. Check and seed 'Pulses' category, Dals, variants and inventory if missing
    existing_pulses = await db.categories.find_one({"slug": "pulses"})
    if not existing_pulses:
        logger.info("Seeding Pulses category, Tuar Dal, Chana Dal and inventory...")
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

        # Locate active shop
        shop = await db.shops.find_one({"isActive": True})
        target_shop_id = shop["_id"] if shop else ObjectId()
        if not shop:
            await db.shops.insert_one({
                "_id": target_shop_id,
                "name": "Kirana Kart Khudel Superstore",
                "slug": "kirana-kart-khudel-superstore",
                "description": "Main quick-delivery hub serving Khudel, Index Medical College, and surrounding corridor",
                "logoUrl": "https://images.unsplash.com/photo-1578916171728-46686eac8d58?w=300",
                "contactPhone": "9876543210",
                "serviceAreaIds": ["indore-launch-area"],
                "supportedPostalCodes": ["453115", "452016", "455223"],
                "timezone": "Asia/Kolkata",
                "isActive": True,
                "acceptsOrders": True,
                "createdAt": now,
                "updatedAt": now,
            })

        # Insert Tuar Dal
        tuar_id = ObjectId()
        v_tuar_500g = ObjectId()
        v_tuar_1kg = ObjectId()
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
                "shopId": target_shop_id,
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
                "shopId": target_shop_id,
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

        # Insert Chana Dal
        chana_id = ObjectId()
        v_chana_500g = ObjectId()
        v_chana_1kg = ObjectId()
        await db.products.insert_one({
            "_id": chana_id,
            "name": "Fortune Unpolished Chana Dal",
            "slug": "chana-dal",
            "shortDescription": "Nutritious and delicious chana dal",
            "description": "Naturally sourced unpolished Chana Dal rich in dietary fibre and protein.",
            "brand": "Fortune",
            "categoryId": pulses_id,
            "imageUrl": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500",
            "images": ["https://images.unsplash.com/photo-1586201375761-83865001e31c?w=500"],
            "searchKeywords": ["chana", "bengal gram", "dal", "pulses"],
            "isActive": True,
            "isFeatured": True,
            "createdAt": now,
            "updatedAt": now,
        })
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
                "shopId": target_shop_id,
                "productId": chana_id,
                "variantId": v_chana_500g,
                "pricePaise": 5500,  # ₹55.00
                "mrpPaise": 6500,  # ₹65.00
                "stockQuantity": 20,
                "reservedQuantity": 0,
                "isAvailable": True,
                "updatedAt": now,
            },
            {
                "shopId": target_shop_id,
                "productId": chana_id,
                "variantId": v_chana_1kg,
                "pricePaise": 10500,  # ₹105.00
                "mrpPaise": 12000,  # ₹120.00
                "stockQuantity": 15,
                "reservedQuantity": 0,
                "isAvailable": True,
                "updatedAt": now,
            },
        ])
        logger.info("Successfully seeded Pulses, Tuar Dal, Chana Dal and variants.")
