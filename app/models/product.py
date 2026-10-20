from datetime import datetime, timezone
from typing import List, Optional, Union
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class ProductInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    name: str
    slug: str
    shortDescription: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    categoryId: Union[ObjectId, str]
    subcategoryId: Optional[Union[ObjectId, str]] = None
    imageUrl: Optional[str] = None
    images: List[str] = Field(default_factory=list)
    searchKeywords: List[str] = Field(default_factory=list)
    isActive: bool = True
    isFeatured: bool = False
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
