from datetime import datetime, timezone
from typing import Optional, Union
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class ProductVariantInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    productId: Union[ObjectId, str]
    sku: str
    variantName: str
    packSize: float
    unit: str  # g, kg, ml, l, piece, etc.
    barcode: Optional[str] = None
    imageUrl: Optional[str] = None
    isActive: bool = True
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
