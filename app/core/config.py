from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Kirna Kart Authentication API"
    APP_ENV: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "kirna_kart"
    MONGODB_MIN_POOL_SIZE: int = 10
    MONGODB_MAX_POOL_SIZE: int = 100
    USE_MOCK_DB: bool = False
    MONGODB_AUTO_FALLBACK_MOCK: bool = True

    # Security & Tokens
    JWT_SECRET_KEY: str = Field(
        default="kirna-kart-dev-insecure-jwt-secret-key-32chars-min-len",
        description="Cryptographic secret key for signing JWTs",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "kirna-kart-api"
    JWT_AUDIENCE: str = "kirna-kart-clients"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # OTP and Verification Tickets
    OTP_EXPIRE_SECONDS: int = 300
    OTP_RESEND_COOLDOWN_SECONDS: int = 30
    OTP_MAX_ATTEMPTS: int = 5
    OTP_HMAC_SECRET: str = Field(
        default="kirna-kart-dev-insecure-otp-hmac-secret-key-32chars",
        description="Keyed HMAC secret for OTP hashes",
    )
    VERIFICATION_TICKET_EXPIRE_SECONDS: int = 300

    # SMS Providers: "mock", "fast2sms", "twilio"
    SMS_PROVIDER: str = "mock"
    DEV_DEFAULT_OTP: Optional[str] = "123456"
    ALLOW_MOCK_SMS_IN_PROD: bool = False
    FAST2SMS_API_KEY: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None

    # Server Port (injected by cloud platforms like Render)
    PORT: int = 8000

    # Redis (distributed rate limiting)
    REDIS_URL: Optional[str] = None

    # CORS
    CORS_ORIGINS: Union[List[str], str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8081"]
    )

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    import json
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    def validate_production_readiness(self) -> None:
        """Validate critical security configurations when running in production."""
        if self.APP_ENV.lower() == "production":
            insecure_defaults = [
                "kirna-kart-dev-insecure-jwt-secret-key-32chars-min-len",
                "replace-with-a-secure-random-secret",
                "replace-with-a-separate-secure-random-secret",
            ]
            if self.JWT_SECRET_KEY in insecure_defaults or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be a unique secure secret of at least 32 characters in production.")
            if self.OTP_HMAC_SECRET in insecure_defaults or len(self.OTP_HMAC_SECRET) < 32:
                raise ValueError("OTP_HMAC_SECRET must be a unique secure secret of at least 32 characters in production.")
            if self.SMS_PROVIDER.lower() == "mock" and not self.ALLOW_MOCK_SMS_IN_PROD:
                raise ValueError("SMS_PROVIDER cannot be 'mock' in production unless ALLOW_MOCK_SMS_IN_PROD=true is explicitly set for testing.")
            if "*" in self.CORS_ORIGINS and not self.ALLOW_MOCK_SMS_IN_PROD:
                raise ValueError("CORS_ORIGINS cannot contain wildcards ('*') in production.")
            if not self.ALLOW_MOCK_SMS_IN_PROD:
                self.DEV_DEFAULT_OTP = None


settings = Settings()
