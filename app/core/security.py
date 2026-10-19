import hashlib
import hmac
import re
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from jose import JWTError, jwt
from app.core.config import settings
from app.core.exceptions import BadRequestException, UnauthorizedException


# Regex for Indian mobile numbers: 10 digits starting with 6-9
INDIAN_MOBILE_REGEX = re.compile(r"^[6-9]\d{9}$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_mobile_number(mobile: str) -> str:
    """
    Validate and normalize Indian mobile numbers to 10 digits.
    Strips whitespace, dashes, '+91', '91', or leading '0'.
    """
    if not mobile or not isinstance(mobile, str):
        raise BadRequestException("Mobile number is required and must be a string.", code="INVALID_MOBILE_NUMBER")

    cleaned = re.sub(r"[\s\-\(\)]", "", mobile.strip())
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = cleaned[1:]

    if not INDIAN_MOBILE_REGEX.match(cleaned):
        raise BadRequestException(
            "Invalid Indian mobile number. Must be a valid 10-digit number starting with 6-9.",
            code="INVALID_MOBILE_NUMBER",
        )
    return cleaned


def normalize_email(email: Optional[str]) -> Optional[str]:
    """Validate and normalize email address to lowercase stripped string."""
    if not email:
        return None
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise BadRequestException("Invalid email format.", code="INVALID_EMAIL_FORMAT")
    return cleaned


def generate_numeric_otp(length: int = 6) -> str:
    """Generate cryptographically secure numeric OTP."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def generate_opaque_token(nbytes: int = 32) -> str:
    """Generate cryptographically secure opaque token string."""
    return secrets.token_urlsafe(nbytes)


def compute_sha256_hash(raw_value: str) -> str:
    """Compute SHA-256 hex digest for high entropy tokens."""
    return hashlib.sha256(raw_value.encode("utf-8")).hexdigest()


def compute_otp_hmac(mobile: str, purpose: str, challenge_id: str, otp: str) -> str:
    """Compute keyed HMAC-SHA256 for an OTP bound to mobile, purpose, and challenge."""
    key = settings.OTP_HMAC_SECRET.encode("utf-8")
    message = f"{mobile}:{purpose}:{challenge_id}:{otp}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_otp_hmac(mobile: str, purpose: str, challenge_id: str, otp: str, expected_hmac: str) -> bool:
    """Constant-time verification of OTP HMAC."""
    computed_hmac = compute_otp_hmac(mobile=mobile, purpose=purpose, challenge_id=challenge_id, otp=otp)
    return hmac.compare_digest(computed_hmac, expected_hmac)


def create_access_token(
    customer_id: str,
    session_id: str,
    role: str = "customer",
    expires_delta: Optional[timedelta] = None,
) -> Tuple[str, int]:
    """Create a signed JWT access token with explicit security claims."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
        expires_in = int(expires_delta.total_seconds())
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    payload = {
        "sub": str(customer_id),
        "sid": str(session_id),
        "role": role,
        "type": "access",
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4()),
    }

    token = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, expires_in


def decode_access_token(token: str) -> Dict[str, Any]:
    """Validate and decode JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
        )
        if payload.get("type") != "access":
            raise UnauthorizedException("Invalid token type. Access token expected.", code="INVALID_TOKEN_TYPE")
        return payload
    except JWTError as exc:
        raise UnauthorizedException(f"Invalid or expired access token: {str(exc)}", code="INVALID_TOKEN")
