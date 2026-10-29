from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CartItemAddRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    productId: str = Field(..., description="Unique product ID")
    variantId: str = Field(..., description="Unique variant ID belonging to the product")
    quantity: int = Field(1, ge=1, le=50, description="Quantity to add (1-50)")
    shopId: Optional[str] = Field(None, description="Optional shop ID context for pricing and inventory")


class CartItemUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    quantity: int = Field(..., ge=1, le=50, description="New quantity (1-50)")


class CartItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    itemId: str
    productId: str
    productName: str
    imageUrl: Optional[str] = None
    variantId: str
    variantName: str
    packSize: Optional[float] = None
    unit: Optional[str] = None
    quantity: int
    unitPricePaise: int
    unitPrice: float
    subtotalPaise: int
    subtotal: float
    inStock: bool
    availableQuantity: int


class CartResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cartId: str
    customerId: Optional[str] = None
    guestCartId: Optional[str] = None
    shopId: Optional[str] = None
    items: List[CartItemResponse] = Field(default_factory=list)
    subtotalPaise: int = 0
    subtotal: float = 0.0
    currency: str = "INR"
    itemCount: int = 0
    totalQuantity: int = 0
    warnings: List[str] = Field(default_factory=list)
    updatedAt: Optional[datetime] = None


class CartValidationItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    itemId: str
    productId: str
    variantId: str
    productName: str
    variantName: str
    status: str
    previousPricePaise: Optional[int] = None
    currentPricePaise: Optional[int] = None
    previousPrice: Optional[float] = None
    currentPrice: Optional[float] = None
    requestedQuantity: int
    availableQuantity: int
    message: Optional[str] = None


class CartValidationResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    valid: bool
    items: List[CartValidationItem] = Field(default_factory=list)
    subtotalPaise: int = 0
    subtotal: float = 0.0
    currency: str = "INR"
    warnings: List[str] = Field(default_factory=list)


class GuestCartMergeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    guestCartId: str = Field(..., description="Secure opaque guest cart identifier")


class GuestCartMergeResponseData(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    merged: bool = True
    itemsMergedCount: int = 0
    cart: CartResponseData
    warnings: List[str] = Field(default_factory=list)
