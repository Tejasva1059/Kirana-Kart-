from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class VerificationTicketInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    tokenHash: str
    mobileNumberNormalized: str
    purpose: str
    expiresAt: datetime
    consumedAt: Optional[datetime] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
