from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.product import PaginationMeta


class ShopListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    slug: str
    logoUrl: Optional[str] = None
    coverImageUrl: Optional[str] = None
    isOpen: bool = True
    acceptsOrders: bool = True
    serviceable: Optional[bool] = None
    serviceAreaIds: List[str] = Field(default_factory=list)
    supportedPostalCodes: List[str] = Field(default_factory=list)
    location: Optional[Dict[str, Any]] = None
    address: Optional[Dict[str, Any]] = None


class ShopListResponseData(BaseModel):
    items: List[ShopListItem] = Field(default_factory=list)
    pagination: PaginationMeta


class ShopDetailResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    slug: str
    description: Optional[str] = None
    logoUrl: Optional[str] = None
    coverImageUrl: Optional[str] = None
    contactPhone: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    serviceAreaIds: List[str] = Field(default_factory=list)
    supportedPostalCodes: List[str] = Field(default_factory=list)
    openingHours: Dict[str, Any] = Field(default_factory=dict)
    timezone: str = "Asia/Kolkata"
    isActive: bool = True
    isOpen: bool = True
    acceptsOrders: bool = True


class ShopAvailabilityResponseData(BaseModel):
    shopId: str
    isActive: bool
    isOpen: bool
    acceptsOrders: bool
    isOrderable: bool
    timezone: str = "Asia/Kolkata"
    nextOpeningAt: Optional[str] = None
    reasonCode: str
