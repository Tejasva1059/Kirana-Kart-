from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pymongo.errors import DuplicateKeyError
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    UnauthorizedException,
)
from app.core.logging import logger
from app.core.security import (
    compute_sha256_hash,
    normalize_email,
    normalize_mobile_number,
)
from app.db.mongodb import get_db, mongo_manager
from app.schemas.auth import (
    AuthResponseData,
    CustomerLoginRequest,
    CustomerSignupRequest,
)
from app.services.customer_service import CustomerService
from app.services.token_service import TokenService


class AuthService:
    @staticmethod
    async def signup_customer(
        request: CustomerSignupRequest,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address_hash: Optional[str] = None,
    ) -> AuthResponseData:
        db = get_db()
        now = datetime.now(timezone.utc)
        normalized_mobile = normalize_mobile_number(request.mobileNumber)
        normalized_email = normalize_email(request.email) if request.email else None

        if not request.acceptedTerms:
            raise BadRequestException("You must accept the terms and conditions to sign up.", code="TERMS_REQUIRED")

        token_hash = compute_sha256_hash(request.verificationToken)

        # 1. Check ticket validity before mutation
        ticket = await db.verification_tickets.find_one({"tokenHash": token_hash})
        if not ticket:
            raise BadRequestException("Invalid or unrecognized verification ticket.", code="INVALID_VERIFICATION_TICKET")

        if ticket.get("consumedAt") is not None:
            raise BadRequestException("Verification ticket has already been used.", code="TICKET_ALREADY_USED")

        expires_at = ticket.get("expiresAt")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                raise BadRequestException("Verification ticket has expired.", code="TICKET_EXPIRED")

        if ticket.get("purpose") != "signup":
            raise BadRequestException("Verification ticket is not valid for signup.", code="INVALID_TICKET_PURPOSE")

        if ticket.get("mobileNumberNormalized") != normalized_mobile:
            raise BadRequestException("Verification ticket does not match the provided mobile number.", code="TICKET_MOBILE_MISMATCH")

        # 2. Check for unique conflicts
        existing_mobile = await db.customers.find_one({"mobileNumberNormalized": normalized_mobile})
        if existing_mobile:
            raise ConflictException("An account with this mobile number already exists.", code="ACCOUNT_ALREADY_EXISTS")

        if normalized_email:
            existing_email = await db.customers.find_one({"emailNormalized": normalized_email})
            if existing_email:
                raise ConflictException("An account with this email address already exists.", code="EMAIL_ALREADY_EXISTS")

        # 3. Create customer document
        # Strictly enforce non-privileged role and server-assigned values
        customer_doc = {
            "fullName": request.fullName.strip(),
            "emailNormalized": normalized_email,
            "mobileNumberNormalized": normalized_mobile,
            "role": "customer",
            "status": "active",
            "mobileVerified": True,
            "emailVerified": False,
            "acceptedTerms": True,
            "termsAcceptedAt": now,
            "termsVersion": "1.0",
            "createdAt": now,
            "updatedAt": now,
            "lastLoginAt": now,
        }

        # 4. Atomic consumption with transaction support when available
        supports_tx = await mongo_manager.supports_transactions()
        if supports_tx and mongo_manager.client:
            async with await mongo_manager.client.start_session() as session:
                async with session.start_transaction():
                    # Consume ticket atomically
                    res = await db.verification_tickets.update_one(
                        {"tokenHash": token_hash, "consumedAt": None},
                        {"$set": {"consumedAt": now}},
                        session=session,
                    )
                    if res.modified_count == 0:
                        raise BadRequestException("Verification ticket was already consumed.", code="TICKET_ALREADY_USED")

                    try:
                        insert_res = await db.customers.insert_one(customer_doc, session=session)
                        customer_doc["_id"] = insert_res.inserted_id
                    except DuplicateKeyError as exc:
                        if "email" in str(exc).lower():
                            raise ConflictException("Email address already registered.", code="EMAIL_ALREADY_EXISTS")
                        raise ConflictException("Mobile number already registered.", code="ACCOUNT_ALREADY_EXISTS")
        else:
            # Standalone fallback: safe conditional atomic consumption followed by rollback if insert fails
            res = await db.verification_tickets.update_one(
                {"tokenHash": token_hash, "consumedAt": None, "expiresAt": {"$gt": now}},
                {"$set": {"consumedAt": now}},
            )
            if res.modified_count == 0:
                raise BadRequestException("Verification ticket has expired or was already consumed.", code="TICKET_ALREADY_USED")

            try:
                insert_res = await db.customers.insert_one(customer_doc)
                customer_doc["_id"] = insert_res.inserted_id
            except DuplicateKeyError as exc:
                # Rollback ticket consumption
                await db.verification_tickets.update_one({"tokenHash": token_hash}, {"$set": {"consumedAt": None}})
                if "email" in str(exc).lower():
                    raise ConflictException("Email address already registered.", code="EMAIL_ALREADY_EXISTS")
                raise ConflictException("Mobile number already registered.", code="ACCOUNT_ALREADY_EXISTS")
            except Exception:
                # Rollback ticket consumption on any unexpected failure
                await db.verification_tickets.update_one({"tokenHash": token_hash}, {"$set": {"consumedAt": None}})
                raise

        # 5. Create session and tokens
        customer_profile = CustomerService.map_to_public_profile(customer_doc)
        token_data = await TokenService.create_session_and_tokens(
            customer_id=str(customer_doc["_id"]),
            role="customer",
            device_info=device_info,
            ip_address_hash=ip_address_hash,
        )

        return AuthResponseData(customer=customer_profile, tokens=token_data)

    @staticmethod
    async def login_customer(
        request: CustomerLoginRequest,
        device_info: Optional[Dict[str, Any]] = None,
        ip_address_hash: Optional[str] = None,
    ) -> AuthResponseData:
        db = get_db()
        now = datetime.now(timezone.utc)
        normalized_mobile = normalize_mobile_number(request.mobileNumber)
        token_hash = compute_sha256_hash(request.verificationToken)

        # 1. Atomically verify and consume login ticket
        ticket = await db.verification_tickets.find_one_and_update(
            {
                "tokenHash": token_hash,
                "consumedAt": None,
                "purpose": "login",
                "mobileNumberNormalized": normalized_mobile,
                "expiresAt": {"$gt": now},
            },
            {"$set": {"consumedAt": now}},
        )

        if not ticket:
            raise UnauthorizedException(
                "Invalid, expired, or already used verification ticket for login.",
                code="INVALID_VERIFICATION_TICKET",
            )

        # 2. Find customer by normalized mobile
        customer = await db.customers.find_one({"mobileNumberNormalized": normalized_mobile})
        if not customer:
            raise UnauthorizedException(
                "Customer account not found. Please sign up first.",
                code="CUSTOMER_NOT_FOUND",
            )

        # 3. Check account status
        if customer.get("status") != "active":
            raise UnauthorizedException(
                "Account is suspended or blocked. Please contact support.",
                code="ACCOUNT_INACTIVE",
            )

        # 4. Update last login timestamp
        await db.customers.update_one({"_id": customer["_id"]}, {"$set": {"lastLoginAt": now}})
        customer["lastLoginAt"] = now

        # 5. Issue session and tokens
        customer_profile = CustomerService.map_to_public_profile(customer)
        token_data = await TokenService.create_session_and_tokens(
            customer_id=str(customer["_id"]),
            role=customer.get("role", "customer"),
            device_info=device_info,
            ip_address_hash=ip_address_hash,
        )

        return AuthResponseData(customer=customer_profile, tokens=token_data)
