from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class OTPChallengeInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    challengeId: str
    mobileNumberNormalized: str
    purpose: str
    otpHmac: str
    expiresAt: datetime
    attemptCount: int = 0
    maxAttempts: int = 5
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lastSentAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    consumedAt: Optional[datetime] = None
    invalidatedAt: Optional[datetime] = None
