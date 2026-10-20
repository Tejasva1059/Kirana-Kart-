from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class GeoJSONPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Point"] = "Point"
    coordinates: List[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Coordinates ordered as [longitude, latitude]",
    )


class AddressInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    customerId: Union[ObjectId, str]
    label: str
    recipientName: str
    recipientMobile: str
    addressLine1: str
    addressLine2: Optional[str] = None
    landmark: Optional[str] = None
    locality: str
    subLocality: Optional[str] = None
    city: str
    district: str
    state: str
    postalCode: str
    country: str = "India"
    formattedAddress: str
    location: Optional[Dict[str, Any]] = None
    isDefault: bool = False
    deliveryInstructions: Optional[str] = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
