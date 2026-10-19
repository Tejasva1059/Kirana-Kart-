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

    logger.info("All collection indexes processed successfully.")
