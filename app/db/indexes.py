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

    # Seed default launch service area
    try:
        from app.services.serviceability_service import ServiceabilityService
        await ServiceabilityService.seed_default_service_areas_if_needed()
    except Exception as exc:
        logger.warning(f"Could not seed default launch service areas: {exc}")

    logger.info("All collection indexes processed successfully.")
