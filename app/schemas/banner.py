from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BannerItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    subtitle: Optional[str] = None
    imageUrl: str
    mobileImageUrl: Optional[str] = None
    targetType: str
    targetId: Optional[str] = None
    targetUrl: Optional[str] = None
    position: int = 1


class BannerListResponseData(BaseModel):
    items: List[BannerItem] = Field(default_factory=list)
