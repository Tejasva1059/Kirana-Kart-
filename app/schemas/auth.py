from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.customer import CustomerPublicProfile


class OTPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobileNumber: str = Field(..., description="10-digit Indian mobile number")
    purpose: Literal["signup", "login"] = Field(..., description="Purpose of the OTP request")


class OTPRequestData(BaseModel):
    challengeId: str
    expiresIn: int
    resendAfter: int


class OTPVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobileNumber: str = Field(..., description="10-digit Indian mobile number")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit numeric OTP")
    purpose: Literal["signup", "login"] = Field(..., description="Purpose of the verification")
    challengeId: str = Field(..., description="Challenge ID received from OTP request")

    @field_validator("otp")
    @classmethod
    def validate_otp_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("OTP must contain only digits.")
        return v


class OTPVerifyData(BaseModel):
    verificationToken: str
    purpose: str
    expiresIn: int


class CustomerSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fullName: str = Field(..., min_length=2, max_length=100, description="Customer's full name")
    email: Optional[str] = Field(None, description="Customer's optional email address")
    mobileNumber: str = Field(..., description="10-digit Indian mobile number")
    verificationToken: str = Field(..., description="Opaque one-time verification ticket")
    acceptedTerms: bool = Field(..., description="Customer agreement to Terms and Conditions")

    @field_validator("fullName")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 100:
            raise ValueError("Full name must be between 2 and 100 characters.")
        return v

    @field_validator("acceptedTerms")
    @classmethod
    def validate_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms and conditions to sign up.")
        return v


class CustomerLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobileNumber: str = Field(..., description="10-digit Indian mobile number")
    verificationToken: str = Field(..., description="Opaque one-time verification ticket with login purpose")


class TokenRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refreshToken: str = Field(..., description="Opaque refresh token")


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refreshToken: str = Field(..., description="Opaque refresh token for the session being terminated")


class TokenData(BaseModel):
    accessToken: str
    tokenType: str = "Bearer"
    expiresIn: int
    refreshToken: str
    refreshExpiresIn: int


class AuthResponseData(BaseModel):
    customer: CustomerPublicProfile
    tokens: TokenData
