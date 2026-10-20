from pymongo import ASCENDING, DESCENDING, IndexModel
from app.core.logging import logger
from app.db.mongodb import get_db


async def create_indexes() -> None:
    """Create all required MongoDB collection indexes idempotently."""
    db = get_db()
    logger.info("Initializing MongoDB indexes...")

    # 1. customers collection indexes
    customers_indexes = [
        IndexModel(
            [("mobileNumberNormalized", ASCENDING)],
            unique=True,
            name="idx_customers_mobile_unique",
        ),
        IndexModel(
            [("emailNormalized", ASCENDING)],
            unique=True,
            partialFilterExpression={"emailNormalized": {"$type": "string"}},
            name="idx_customers_email_partial_unique",
        ),
        IndexModel([("status", ASCENDING)], name="idx_customers_status"),
        IndexModel([("createdAt", DESCENDING)], name="idx_customers_created_at"),
    ]
    try:
        await db.customers.create_indexes(customers_indexes)
        logger.info("Created indexes for 'customers' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'customers' collection: {exc}")

    # 2. otp_challenges collection indexes
    otp_indexes = [
        IndexModel([("challengeId", ASCENDING)], unique=True, name="idx_otp_challenge_id_unique"),
        IndexModel(
            [("mobileNumberNormalized", ASCENDING), ("purpose", ASCENDING), ("createdAt", DESCENDING)],
            name="idx_otp_mobile_purpose_created",
        ),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=0, name="idx_otp_ttl_expires"),
    ]
    try:
        await db.otp_challenges.create_indexes(otp_indexes)
        logger.info("Created indexes for 'otp_challenges' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'otp_challenges' collection: {exc}")

    # 3. verification_tickets collection indexes
    ticket_indexes = [
        IndexModel([("tokenHash", ASCENDING)], unique=True, name="idx_ticket_token_hash_unique"),
        IndexModel(
            [("mobileNumberNormalized", ASCENDING), ("purpose", ASCENDING)],
            name="idx_ticket_mobile_purpose",
        ),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=0, name="idx_ticket_ttl_expires"),
    ]
    try:
        await db.verification_tickets.create_indexes(ticket_indexes)
        logger.info("Created indexes for 'verification_tickets' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'verification_tickets' collection: {exc}")

    # 4. auth_sessions collection indexes
    session_indexes = [
        IndexModel([("sessionId", ASCENDING)], unique=True, name="idx_session_id_unique"),
        IndexModel([("refreshTokenHash", ASCENDING)], name="idx_session_refresh_token_hash"),
        IndexModel([("customerId", ASCENDING)], name="idx_session_customer_id"),
        IndexModel([("expiresAt", ASCENDING)], expireAfterSeconds=0, name="idx_session_ttl_expires"),
        IndexModel([("revokedAt", ASCENDING)], name="idx_session_revoked_at"),
    ]
    try:
        await db.auth_sessions.create_indexes(session_indexes)
        logger.info("Created indexes for 'auth_sessions' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'auth_sessions' collection: {exc}")

    # 5. addresses collection indexes
    address_indexes = [
        IndexModel(
            [("customerId", ASCENDING), ("isDefault", DESCENDING), ("updatedAt", DESCENDING)],
            name="idx_addresses_customer_default_updated",
        ),
        IndexModel(
            [("customerId", ASCENDING), ("_id", ASCENDING)],
            name="idx_addresses_customer_id_lookup",
        ),
        IndexModel([("location", "2dsphere")], name="idx_addresses_location_2dsphere"),
    ]
    try:
        await db.addresses.create_indexes(address_indexes)
        logger.info("Created indexes for 'addresses' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'addresses' collection: {exc}")

    # 6. service_areas collection indexes
    service_area_indexes = [
        IndexModel([("serviceAreaId", ASCENDING)], unique=True, name="idx_service_area_id_unique"),
        IndexModel([("enabled", ASCENDING)], name="idx_service_area_enabled"),
        IndexModel([("pincodes", ASCENDING)], name="idx_service_area_pincodes"),
        IndexModel([("polygon", "2dsphere")], name="idx_service_area_polygon_2dsphere"),
    ]
    try:
        await db.service_areas.create_indexes(service_area_indexes)
        logger.info("Created indexes for 'service_areas' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'service_areas' collection: {exc}")

    # 7. banners collection indexes
    banner_indexes = [
        IndexModel([("isActive", ASCENDING), ("position", ASCENDING)], name="idx_banners_active_position"),
        IndexModel([("serviceAreaIds", ASCENDING)], name="idx_banners_service_areas"),
        IndexModel([("startsAt", ASCENDING), ("endsAt", ASCENDING)], name="idx_banners_schedule"),
    ]
    try:
        await db.banners.create_indexes(banner_indexes)
        logger.info("Created indexes for 'banners' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'banners' collection: {exc}")

    # 8. categories collection indexes
    category_indexes = [
        IndexModel([("slug", ASCENDING)], unique=True, name="idx_categories_slug_unique"),
        IndexModel(
            [("parentCategoryId", ASCENDING), ("isActive", ASCENDING), ("sortOrder", ASCENDING)],
            name="idx_categories_parent_active_sort",
        ),
        IndexModel(
            [("isActive", ASCENDING), ("isFeatured", ASCENDING), ("sortOrder", ASCENDING)],
            name="idx_categories_active_featured_sort",
        ),
    ]
    try:
        await db.categories.create_indexes(category_indexes)
        logger.info("Created indexes for 'categories' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'categories' collection: {exc}")

    # 9. products collection indexes
    product_indexes = [
        IndexModel([("slug", ASCENDING)], unique=True, name="idx_products_slug_unique"),
        IndexModel([("categoryId", ASCENDING), ("isActive", ASCENDING)], name="idx_products_category_active"),
        IndexModel([("subcategoryId", ASCENDING), ("isActive", ASCENDING)], name="idx_products_subcategory_active"),
        IndexModel([("isActive", ASCENDING), ("isFeatured", ASCENDING)], name="idx_products_active_featured"),
        IndexModel([("searchKeywords", ASCENDING)], name="idx_products_keywords"),
    ]
    try:
        await db.products.create_indexes(product_indexes)
        logger.info("Created indexes for 'products' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'products' collection: {exc}")

    # 10. product_variants collection indexes
    variant_indexes = [
        IndexModel([("sku", ASCENDING)], unique=True, name="idx_variants_sku_unique"),
        IndexModel([("productId", ASCENDING), ("isActive", ASCENDING)], name="idx_variants_product_active"),
    ]
    try:
        await db.product_variants.create_indexes(variant_indexes)
        logger.info("Created indexes for 'product_variants' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'product_variants' collection: {exc}")

    # 11. shops collection indexes
    shop_indexes = [
        IndexModel([("slug", ASCENDING)], unique=True, name="idx_shops_slug_unique"),
        IndexModel([("isActive", ASCENDING), ("acceptsOrders", ASCENDING)], name="idx_shops_active_orders"),
        IndexModel([("serviceAreaIds", ASCENDING)], name="idx_shops_service_areas"),
        IndexModel([("supportedPostalCodes", ASCENDING)], name="idx_shops_postal_codes"),
        IndexModel([("location", "2dsphere")], name="idx_shops_location_2dsphere"),
    ]
    try:
        await db.shops.create_indexes(shop_indexes)
        logger.info("Created indexes for 'shops' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'shops' collection: {exc}")

    # 12. shop_inventory collection indexes
    inventory_indexes = [
        IndexModel([("shopId", ASCENDING), ("variantId", ASCENDING)], unique=True, name="idx_inventory_shop_variant_unique"),
        IndexModel([("shopId", ASCENDING), ("productId", ASCENDING)], name="idx_inventory_shop_product"),
        IndexModel([("shopId", ASCENDING), ("isAvailable", ASCENDING), ("pricePaise", ASCENDING)], name="idx_inventory_shop_avail_price"),
    ]
    try:
        await db.shop_inventory.create_indexes(inventory_indexes)
        logger.info("Created indexes for 'shop_inventory' collection.")
    except Exception as exc:
        logger.warning(f"Could not create indexes for 'shop_inventory' collection: {exc}")

    # Seed default launch service area & catalogue
    try:
        from app.services.serviceability_service import ServiceabilityService
        await ServiceabilityService.seed_default_service_areas_if_needed()
    except Exception as exc:
        logger.warning(f"Could not seed default launch service areas: {exc}")

    try:
        from app.services.catalogue_seed import seed_default_catalogue_if_needed
        await seed_default_catalogue_if_needed()
    except Exception as exc:
        logger.warning(f"Could not seed default launch catalogue: {exc}")

    logger.info("All collection indexes processed successfully.")
