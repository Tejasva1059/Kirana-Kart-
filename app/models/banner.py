from datetime import datetime, timezone
from typing import List, Literal, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


BannerTargetType = Literal["category", "product", "shop", "collection", "external_url", "none"]


class BannerInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    title: str
    subtitle: Optional[str] = None
    imageUrl: str
    mobileImageUrl: Optional[str] = None
    targetType: BannerTargetType = "none"
    targetId: Optional[str] = None
    targetUrl: Optional[str] = None
    position: int = 1
    isActive: bool = True
    startsAt: Optional[datetime] = None
    endsAt: Optional[datetime] = None
    serviceAreaIds: Optional[List[str]] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
