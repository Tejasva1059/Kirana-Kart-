from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.variant import ProductVariantItem


class ProductPrice(BaseModel):
    amountPaise: int
    mrpPaise: Optional[int] = None
    currency: str = "INR"


class ProductAvailabilitySummary(BaseModel):
    isAvailable: bool = False
    availableQuantity: int = 0
    reasonCode: Optional[str] = None


class PaginationMeta(BaseModel):
    total: int = 0
    limit: int = 20
    offset: int = 0
    hasMore: bool = False


class ProductListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    slug: str
    brand: Optional[str] = None
    categoryId: str
    subcategoryId: Optional[str] = None
    imageUrl: Optional[str] = None
    price: Optional[ProductPrice] = None
    availability: Optional[ProductAvailabilitySummary] = None
    variants: List[ProductVariantItem] = Field(default_factory=list)


class ProductListResponseData(BaseModel):
    items: List[ProductListItem] = Field(default_factory=list)
    pagination: PaginationMeta


class ProductDetailResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    slug: str
    shortDescription: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    categoryId: str
    subcategoryId: Optional[str] = None
    imageUrl: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    variants: List[ProductVariantItem] = Field(default_factory=list)
    selectedShop: Optional[Dict[str, Any]] = None
    price: Optional[ProductPrice] = None
    availability: Optional[ProductAvailabilitySummary] = None


class ProductAvailabilityResponseData(BaseModel):
    productId: str
    shopId: Optional[str] = None
    variantId: Optional[str] = None
    isAvailable: bool
    availableQuantity: int
    pricePaise: Optional[int] = None
    mrpPaise: Optional[int] = None
    currency: str = "INR"
    reasonCode: str
