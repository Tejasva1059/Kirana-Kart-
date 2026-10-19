import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
from pymongo import ReturnDocument
from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.logging import logger
from app.core.security import (
    compute_sha256_hash,
    create_access_token,
    generate_opaque_token,
)
from app.db.mongodb import get_db
from app.schemas.auth import TokenData


class TokenService:
    @staticmethod
    async def create_session_and_tokens(
        customer_id: str,
        role: str = "customer",
        device_info: Optional[Dict[str, Any]] = None,
        ip_address_hash: Optional[str] = None,
    ) -> TokenData:
        db = get_db()
        now = datetime.now(timezone.utc)
        session_id = str(uuid.uuid4())

        # Opaque 48-byte refresh token
        raw_refresh_token = generate_opaque_token(48)
        refresh_token_hash = compute_sha256_hash(raw_refresh_token)
        refresh_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        session_doc = {
            "sessionId": session_id,
            "customerId": str(customer_id),
            "refreshTokenHash": refresh_token_hash,
            "createdAt": now,
            "expiresAt": refresh_expires_at,
            "lastUsedAt": now,
            "revokedAt": None,
            "replacedBySessionOrTokenId": None,
            "deviceInfo": device_info,
            "ipAddressHash": ip_address_hash,
        }
        await db.auth_sessions.insert_one(session_doc)

        access_token, access_expires_in = create_access_token(
            customer_id=str(customer_id),
            session_id=session_id,
            role=role,
        )

        return TokenData(
            accessToken=access_token,
            tokenType="Bearer",
            expiresIn=access_expires_in,
            refreshToken=raw_refresh_token,
            refreshExpiresIn=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

    @staticmethod
    async def rotate_refresh_token(raw_refresh_token: str) -> TokenData:
        db = get_db()
        now = datetime.now(timezone.utc)
        token_hash = compute_sha256_hash(raw_refresh_token)

        # 1. Lookup session by current token hash
        session = await db.auth_sessions.find_one({"refreshTokenHash": token_hash})

        if not session:
            # Check for token reuse in superseded tokens
            reused_session = await db.auth_sessions.find_one({"replacedBySessionOrTokenId": token_hash})
            if reused_session:
                customer_id = reused_session.get("customerId")
                logger.warning(
                    f"POTENTIAL REFRESH TOKEN REUSE DETECTED for customer {customer_id}! Revoking all sessions."
                )
                await db.auth_sessions.update_many(
                    {"customerId": customer_id, "revokedAt": None},
                    {"$set": {"revokedAt": now}},
                )
                raise UnauthorizedException(
                    "Suspicious token reuse detected. All active sessions have been revoked for your safety.",
                    code="TOKEN_REUSE_DETECTED",
                )
            raise UnauthorizedException("Invalid refresh token.", code="INVALID_REFRESH_TOKEN")

        # 2. Check if already revoked
        if session.get("revokedAt") is not None:
            raise UnauthorizedException("Session has been revoked.", code="SESSION_REVOKED")

        # 3. Check expiration
        expires_at = session.get("expiresAt")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                raise UnauthorizedException("Refresh token has expired.", code="TOKEN_EXPIRED")

        # 4. Verify customer status
        customer_id_str = session.get("customerId")
        customer_query: Dict[str, Any] = {}
        if ObjectId.is_valid(customer_id_str):
            customer_query = {"_id": ObjectId(customer_id_str)}
        else:
            customer_query = {"_id": customer_id_str}

        customer = await db.customers.find_one(customer_query)
        if not customer or customer.get("status") != "active":
            raise UnauthorizedException("Customer account is blocked or inactive.", code="ACCOUNT_INACTIVE")

        # 5. Atomically rotate the refresh token
        new_raw_refresh_token = generate_opaque_token(48)
        new_token_hash = compute_sha256_hash(new_raw_refresh_token)
        new_refresh_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        updated_session = await db.auth_sessions.find_one_and_update(
            {
                "sessionId": session["sessionId"],
                "refreshTokenHash": token_hash,
                "revokedAt": None,
            },
            {
                "$set": {
                    "refreshTokenHash": new_token_hash,
                    "lastUsedAt": now,
                    "expiresAt": new_refresh_expires_at,
                    "replacedBySessionOrTokenId": token_hash,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        if not updated_session:
            raise UnauthorizedException("Refresh token rotation conflict.", code="TOKEN_ROTATION_CONFLICT")

        access_token, access_expires_in = create_access_token(
            customer_id=customer_id_str,
            session_id=session["sessionId"],
            role=customer.get("role", "customer"),
        )

        return TokenData(
            accessToken=access_token,
            tokenType="Bearer",
            expiresIn=access_expires_in,
            refreshToken=new_raw_refresh_token,
            refreshExpiresIn=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

    @staticmethod
    async def revoke_session(raw_refresh_token: str, customer_id: str, session_id: Optional[str] = None) -> bool:
        db = get_db()
        now = datetime.now(timezone.utc)
        token_hash = compute_sha256_hash(raw_refresh_token)

        query: Dict[str, Any] = {
            "refreshTokenHash": token_hash,
            "customerId": str(customer_id),
        }
        if session_id:
            query["sessionId"] = session_id

        # Idempotent revocation
        result = await db.auth_sessions.update_one(query, {"$set": {"revokedAt": now}})
        return result.modified_count > 0 or result.matched_count > 0

    @staticmethod
    async def is_session_active(session_id: str, customer_id: str) -> bool:
        db = get_db()
        now = datetime.now(timezone.utc)
        session = await db.auth_sessions.find_one({
            "sessionId": session_id,
            "customerId": str(customer_id),
            "revokedAt": None,
            "expiresAt": {"$gt": now},
        })
        return session is not None
