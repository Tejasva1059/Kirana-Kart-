from datetime import datetime, timedelta, timezone
from typing import Optional
from pymongo import ReturnDocument
from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ServiceUnavailableException,
)
from app.core.logging import logger
from app.core.security import (
    compute_otp_hmac,
    compute_sha256_hash,
    generate_numeric_otp,
    generate_opaque_token,
    normalize_mobile_number,
    verify_otp_hmac,
)
from app.db.mongodb import get_db
from app.schemas.auth import OTPRequestData, OTPVerifyData
from app.services.sms_service import get_sms_provider


class OTPService:
    @staticmethod
    async def request_otp(mobile_number: str, purpose: str, client_ip: Optional[str] = None) -> OTPRequestData:
        normalized_mobile = normalize_mobile_number(mobile_number)
        db = get_db()
        now = datetime.now(timezone.utc)

        # 1. Signup verification: prevent issuance if customer already exists
        if purpose == "signup":
            existing = await db.customers.find_one({"mobileNumberNormalized": normalized_mobile})
            if existing:
                raise ConflictException(
                    "An account with this mobile number already exists. Please login instead.",
                    code="ACCOUNT_ALREADY_EXISTS",
                )

        # 2. Login verification: account enumeration protection
        # If customer does not exist or is blocked/suspended, return generic response without sending SMS
        if purpose == "login":
            existing = await db.customers.find_one({"mobileNumberNormalized": normalized_mobile})
            if not existing or existing.get("status") != "active":
                logger.info(f"Login OTP suppressed for unverified/inactive/nonexistent mobile: ...{normalized_mobile[-4:]}")
                # Create a blackhole dummy challenge ID to maintain consistent response timing and shape
                dummy_challenge_id = generate_opaque_token(24)
                return OTPRequestData(
                    challengeId=dummy_challenge_id,
                    expiresIn=settings.OTP_EXPIRE_SECONDS,
                    resendAfter=settings.OTP_RESEND_COOLDOWN_SECONDS,
                )

        # 3. Check resend cooldown on the most recent challenge for this mobile and purpose
        latest_challenge = await db.otp_challenges.find_one(
            {"mobileNumberNormalized": normalized_mobile, "purpose": purpose},
            sort=[("createdAt", -1)],
        )
        if latest_challenge:
            created_at = latest_challenge.get("createdAt")
            if created_at:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                elapsed = (now - created_at).total_seconds()
                if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
                    wait_seconds = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                    raise BadRequestException(
                        f"Please wait {wait_seconds} seconds before requesting a new OTP.",
                        code="OTP_RESEND_COOLDOWN",
                        details=[{"resendAfter": wait_seconds}],
                    )

        # 4. Invalidate previous active challenges for this mobile and purpose
        await db.otp_challenges.update_many(
            {
                "mobileNumberNormalized": normalized_mobile,
                "purpose": purpose,
                "consumedAt": None,
                "invalidatedAt": None,
            },
            {"$set": {"invalidatedAt": now}},
        )

        # 5. Generate secure 6-digit OTP and opaque challenge ID
        otp = generate_numeric_otp(6)
        challenge_id = generate_opaque_token(24)
        otp_hmac = compute_otp_hmac(
            mobile=normalized_mobile,
            purpose=purpose,
            challenge_id=challenge_id,
            otp=otp,
        )

        # 6. Save OTP challenge document
        expires_at = now + timedelta(seconds=settings.OTP_EXPIRE_SECONDS)
        challenge_doc = {
            "challengeId": challenge_id,
            "mobileNumberNormalized": normalized_mobile,
            "purpose": purpose,
            "otpHmac": otp_hmac,
            "expiresAt": expires_at,
            "attemptCount": 0,
            "maxAttempts": settings.OTP_MAX_ATTEMPTS,
            "createdAt": now,
            "lastSentAt": now,
            "consumedAt": None,
            "invalidatedAt": None,
        }
        await db.otp_challenges.insert_one(challenge_doc)

        # 7. Dispatch SMS through configured provider
        sms_provider = get_sms_provider()
        sent = await sms_provider.send_otp(normalized_mobile, otp, purpose)
        if not sent:
            # Mark challenge as invalidated if provider failed
            await db.otp_challenges.update_one({"challengeId": challenge_id}, {"$set": {"invalidatedAt": now}})
            raise ServiceUnavailableException(
                "Unable to deliver OTP SMS at this time. Please try again later.",
                code="SMS_DELIVERY_FAILED",
            )

        return OTPRequestData(
            challengeId=challenge_id,
            expiresIn=settings.OTP_EXPIRE_SECONDS,
            resendAfter=settings.OTP_RESEND_COOLDOWN_SECONDS,
        )

    @staticmethod
    async def verify_otp(
        mobile_number: str,
        otp: str,
        purpose: str,
        challenge_id: str,
    ) -> OTPVerifyData:
        normalized_mobile = normalize_mobile_number(mobile_number)
        db = get_db()
        now = datetime.now(timezone.utc)

        challenge = await db.otp_challenges.find_one({"challengeId": challenge_id})
        if not challenge:
            raise BadRequestException("Invalid or expired OTP challenge.", code="INVALID_OR_EXPIRED_OTP")

        # Purpose and mobile binding verification
        if challenge.get("mobileNumberNormalized") != normalized_mobile or challenge.get("purpose") != purpose:
            raise BadRequestException(
                "OTP challenge does not match the provided mobile number or purpose.",
                code="INVALID_OR_EXPIRED_OTP",
            )

        # Check if already consumed or invalidated
        if challenge.get("consumedAt") is not None:
            raise BadRequestException("This OTP has already been used.", code="OTP_ALREADY_USED")

        if challenge.get("invalidatedAt") is not None:
            raise BadRequestException("This OTP challenge has been invalidated.", code="OTP_INVALIDATED")

        # Expiry check
        expires_at = challenge.get("expiresAt")
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                raise BadRequestException("OTP has expired. Please request a new one.", code="OTP_EXPIRED")

        # Max attempts check
        current_attempts = challenge.get("attemptCount", 0)
        max_attempts = challenge.get("maxAttempts", settings.OTP_MAX_ATTEMPTS)
        if current_attempts >= max_attempts:
            await db.otp_challenges.update_one({"challengeId": challenge_id}, {"$set": {"invalidatedAt": now}})
            raise BadRequestException("Maximum verification attempts exceeded.", code="MAX_ATTEMPTS_EXCEEDED")

        # Atomically increment attempt count
        updated_challenge = await db.otp_challenges.find_one_and_update(
            {
                "challengeId": challenge_id,
                "consumedAt": None,
                "invalidatedAt": None,
                "attemptCount": {"$lt": max_attempts},
            },
            {"$inc": {"attemptCount": 1}},
            return_document=ReturnDocument.AFTER,
        )

        if not updated_challenge:
            raise BadRequestException("Maximum verification attempts exceeded.", code="MAX_ATTEMPTS_EXCEEDED")

        # Constant-time HMAC comparison
        is_valid = verify_otp_hmac(
            mobile=normalized_mobile,
            purpose=purpose,
            challenge_id=challenge_id,
            otp=otp,
            expected_hmac=challenge["otpHmac"],
        )

        # In development or testing with mock SMS provider, also accept DEV_DEFAULT_OTP (e.g. '123456')
        if (
            not is_valid
            and (settings.APP_ENV == "development" or settings.ALLOW_MOCK_SMS_IN_PROD)
            and settings.SMS_PROVIDER == "mock"
            and settings.DEV_DEFAULT_OTP
            and otp == settings.DEV_DEFAULT_OTP
        ):
            is_valid = True

        if not is_valid:
            attempts_made = updated_challenge.get("attemptCount", 1)
            if attempts_made >= max_attempts:
                await db.otp_challenges.update_one({"challengeId": challenge_id}, {"$set": {"invalidatedAt": now}})
                raise BadRequestException(
                    "Incorrect OTP. Maximum verification attempts reached. Challenge invalidated.",
                    code="MAX_ATTEMPTS_EXCEEDED",
                )
            remaining = max_attempts - attempts_made
            raise BadRequestException(
                f"Incorrect OTP. {remaining} attempt(s) remaining.",
                code="INCORRECT_OTP",
                details=[{"remainingAttempts": remaining}],
            )

        # Consume challenge atomically
        consume_result = await db.otp_challenges.update_one(
            {"challengeId": challenge_id, "consumedAt": None},
            {"$set": {"consumedAt": now}},
        )
        if consume_result.modified_count == 0:
            raise BadRequestException("OTP was already consumed.", code="OTP_ALREADY_USED")

        # Issue one-time opaque verification ticket
        raw_verification_token = generate_opaque_token(32)
        token_hash = compute_sha256_hash(raw_verification_token)
        ticket_doc = {
            "tokenHash": token_hash,
            "mobileNumberNormalized": normalized_mobile,
            "purpose": purpose,
            "expiresAt": now + timedelta(seconds=settings.VERIFICATION_TICKET_EXPIRE_SECONDS),
            "consumedAt": None,
            "createdAt": now,
        }
        await db.verification_tickets.insert_one(ticket_doc)

        return OTPVerifyData(
            verificationToken=raw_verification_token,
            purpose=purpose,
            expiresIn=settings.VERIFICATION_TICKET_EXPIRE_SECONDS,
        )
