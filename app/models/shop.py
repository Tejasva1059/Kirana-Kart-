from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class ShopInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    name: str
    slug: str
    description: Optional[str] = None
    logoUrl: Optional[str] = None
    coverImageUrl: Optional[str] = None
    contactPhone: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None  # GeoJSON Point
    serviceAreaIds: List[str] = Field(default_factory=list)
    supportedPostalCodes: List[str] = Field(default_factory=list)
    openingHours: Dict[str, Any] = Field(default_factory=dict)
    timezone: str = "Asia/Kolkata"
    isActive: bool = True
    acceptsOrders: bool = True
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
