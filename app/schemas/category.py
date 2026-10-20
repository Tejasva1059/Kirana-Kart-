from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CategoryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    slug: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    iconUrl: Optional[str] = None
    parentCategoryId: Optional[str] = None
    sortOrder: int = 1
    isFeatured: bool = False
    subcategories: Optional[List["CategoryItem"]] = None


class CategoryListResponseData(BaseModel):
    items: List[CategoryItem] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


CategoryItem.model_rebuild()
