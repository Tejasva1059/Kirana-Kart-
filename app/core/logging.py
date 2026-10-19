import logging
import re
import sys
from typing import Any, Dict

SENSITIVE_PATTERNS = [
    re.compile(r'(?i)("?(?:otp|code|verificationToken|refreshToken|accessToken|password|secret|apiKey|api_key|authToken|auth_token)"?\s*[:=]\s*["\'])([^"\']+)(["\'])'),
    re.compile(r'(?i)(bearer\s+)([a-zA-Z0-9_\-\.]+)', re.IGNORECASE),
]

SENSITIVE_KEYS = {
    "otp",
    "code",
    "verificationtoken",
    "verification_token",
    "refreshtoken",
    "refresh_token",
    "accesstoken",
    "access_token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "auth_token",
    "authorization",
}


def redact_sensitive_str(text: str) -> str:
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1***REDACTED***\3" if pattern.groups == 3 else r"\1***REDACTED***", redacted)
    return redacted


def redact_sensitive_dict(data: Any) -> Any:
    if isinstance(data, dict):
        clean = {}
        for k, v in data.items():
            if str(k).lower().replace("_", "") in SENSITIVE_KEYS:
                clean[k] = "***REDACTED***"
            else:
                clean[k] = redact_sensitive_dict(v)
        return clean
    elif isinstance(data, list):
        return [redact_sensitive_dict(item) for item in data]
    elif isinstance(data, str):
        return redact_sensitive_str(data)
    return data


class SensitiveRedactionFormatter(logging.Formatter):
    """Custom formatter that automatically redacts sensitive tokens, OTPs, and keys."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact_sensitive_str(original)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("kirana_kart")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        formatter = SensitiveRedactionFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logging()
