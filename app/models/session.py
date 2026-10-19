from datetime import datetime, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class AuthSessionInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    sessionId: str
    customerId: str
    refreshTokenHash: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expiresAt: datetime
    lastUsedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    revokedAt: Optional[datetime] = None
    replacedBySessionOrTokenId: Optional[str] = None
    deviceInfo: Optional[Dict[str, Any]] = None
    ipAddressHash: Optional[str] = None
