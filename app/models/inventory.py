from datetime import datetime, timezone
from typing import Optional, Union
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShopInventoryInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    shopId: Union[ObjectId, str]
    productId: Union[ObjectId, str]
    variantId: Union[ObjectId, str]
    pricePaise: int = Field(ge=0)
    mrpPaise: Optional[int] = Field(default=None, ge=0)
    stockQuantity: int = Field(default=0, ge=0)
    reservedQuantity: int = Field(default=0, ge=0)
    isAvailable: bool = True
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_mrp(self) -> "ShopInventoryInDB":
        if self.mrpPaise is not None and self.mrpPaise < self.pricePaise:
            raise ValueError("mrpPaise cannot be less than selling pricePaise")
        return self

    @property
    def availableQuantity(self) -> int:
        return max(self.stockQuantity - self.reservedQuantity, 0)
