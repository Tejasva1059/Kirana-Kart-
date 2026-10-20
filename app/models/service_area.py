from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class ServiceAreaInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    serviceAreaId: str
    name: str
    enabled: bool = True
    deliveryCharge: int = 0
    currency: str = "INR"
    pincodes: List[str] = Field(default_factory=list)
    localities: List[str] = Field(default_factory=list)
    polygon: Optional[Dict[str, Any]] = None  # GeoJSON Polygon
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
