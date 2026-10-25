from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import ApiResponse
from app.schemas.product import (
    PaginationMeta,
    ProductAvailabilitySummary,
    ProductPrice,
)
from app.schemas.variant import ProductVariantItem


class SearchCategoryItem(BaseModel):
    id: str
    name: str
    slug: Optional[str] = None


class SearchProductItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    productId: str
    name: str
    slug: str
    imageUrl: Optional[str] = None
    category: Optional[SearchCategoryItem] = None
    categoryId: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[ProductPrice] = None
    pricePaise: Optional[int] = None
    inStock: bool = False
    availability: Optional[ProductAvailabilitySummary] = None
    variants: List[ProductVariantItem] = Field(default_factory=list)


class SearchResponseData(BaseModel):
    query: str
    items: List[SearchProductItem] = Field(default_factory=list)
    pagination: PaginationMeta


class SearchProductsResponse(ApiResponse[SearchResponseData]):
    query: Optional[str] = None
    pagination: Optional[PaginationMeta] = None


class SearchSuggestionItem(BaseModel):
    text: str
    type: str  # "product", "category", "brand"
    id: Optional[str] = None
    imageUrl: Optional[str] = None


class SearchSuggestionsResponseData(BaseModel):
    query: str
    suggestions: List[SearchSuggestionItem] = Field(default_factory=list)


class SearchSuggestionsResponse(ApiResponse[SearchSuggestionsResponseData]):
    query: Optional[str] = None
    suggestions: Optional[List[SearchSuggestionItem]] = None


class TrendingSearchItem(BaseModel):
    query: str
    searchCount: int
