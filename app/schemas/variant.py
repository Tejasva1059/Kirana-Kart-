from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ProductVariantItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    productId: Optional[str] = None
    variantName: str
    packSize: float
    unit: str
    sku: str
    barcode: Optional[str] = None
    imageUrl: Optional[str] = None
    pricePaise: Optional[int] = None
    mrpPaise: Optional[int] = None
    availableQuantity: Optional[int] = None
    isAvailable: Optional[bool] = None


class VariantListResponseData(BaseModel):
    items: List[ProductVariantItem] = Field(default_factory=list)
