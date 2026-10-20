from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class LocationSearchCoordinate(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LocationSearchItem(BaseModel):
    placeId: str
    name: str
    formattedAddress: str
    locality: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    location: LocationSearchCoordinate
    isServiceable: bool = False


class LocationSearchResponseData(BaseModel):
    items: List[LocationSearchItem]
    provider: str
