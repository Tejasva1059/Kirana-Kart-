from datetime import datetime, timezone
from typing import Any, Optional, Union
from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field


class CategoryInDB(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(default=None, alias="_id")
    name: str
    slug: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    iconUrl: Optional[str] = None
    parentCategoryId: Optional[Union[ObjectId, str]] = None
    sortOrder: int = 1
    isActive: bool = True
    isFeatured: bool = False
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
