from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class CustomerInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    fullName: str
    emailNormalized: Optional[str] = None
    mobileNumberNormalized: str
    role: str = "customer"
    status: str = "active"
    mobileVerified: bool = True
    emailVerified: bool = False
    acceptedTerms: bool = True
    termsAcceptedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    termsVersion: str = "1.0"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lastLoginAt: Optional[datetime] = None
