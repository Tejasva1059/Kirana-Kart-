from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class WishlistItemAddRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    productId: str = Field(..., description="Unique product ID to add to wishlist")


class WishlistItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    productId: str
    productName: str
    slug: str
    brand: Optional[str] = None
    categoryId: str
    imageUrl: Optional[str] = None
    pricePaise: Optional[int] = None
    price: Optional[float] = None
    mrpPaise: Optional[int] = None
    isAvailable: bool = True
    availableQuantity: int = 0
    addedAt: datetime


class WishlistResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    wishlistId: str
    customerId: str
    items: List[WishlistItemResponse] = Field(default_factory=list)
    totalCount: int = 0
