from typing import List, Optional
from fastapi import APIRouter, Query, Request
from app.schemas.common import ApiResponse
from app.schemas.search import (
    SearchProductsResponse,
    SearchResponseData,
    SearchSuggestionsResponse,
    SearchSuggestionsResponseData,
    TrendingSearchItem,
)
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get(
    "",
    response_model=SearchProductsResponse,
    summary="Search grocery products",
    description="Case-insensitive grocery product search matching product names, brands, keywords, SKUs, and categories with ranking, shop pricing, and stock status.",
)
async def search_products(
    request: Request,
    q: str = Query(..., description="Required search text (trimmed, non-empty)"),
    page: int = Query(1, description="Page number (1-indexed, default 1)"),
    limit: int = Query(20, description="Items per page (default 20, max 50)"),
    categoryId: Optional[str] = Query(None, description="Category filter"),
    shopId: Optional[str] = Query(None, description="Selected shop identifier for price and inventory scoping"),
    serviceAreaId: Optional[str] = Query(None, description="Service area identifier to resolve eligible shops"),
    brand: Optional[str] = Query(None, description="Brand filter"),
    inStock: Optional[bool] = Query(None, description="Stock filter (true for in-stock only, false for out-of-stock only)"),
    sortBy: str = Query("relevance", description="Sort order: relevance, price_asc, price_desc, name_asc, newest"),
    minPrice: Optional[int] = Query(None, description="Minimum price in paise"),
    maxPrice: Optional[int] = Query(None, description="Maximum price in paise"),
) -> SearchProductsResponse:
    items, pagination = await SearchService.search_products(
        q=q,
        category_id=categoryId,
        shop_id=shopId,
        service_area_id=serviceAreaId,
        brand=brand,
        in_stock=inStock,
        sort_by=sortBy,
        min_price=minPrice,
        max_price=maxPrice,
        page=page,
        limit=limit,
    )

    clean_q = q.strip()
    data_payload = SearchResponseData(
        query=clean_q,
        items=items,
        pagination=pagination,
    )
    return SearchProductsResponse(
        success=True,
        message="Search results fetched successfully.",
        query=clean_q,
        pagination=pagination,
        data=data_payload,
    )


@router.get(
    "/suggestions",
    response_model=SearchSuggestionsResponse,
    summary="Autocomplete suggestions",
    description="Returns lightweight autocomplete suggestions across product names, categories, and brands (min 2 characters, max 10 suggestions).",
)
async def get_suggestions(
    q: str = Query("", description="Query text (minimum 2 characters for suggestions)"),
    limit: int = Query(10, ge=1, le=10, description="Maximum suggestions to return (default 10, max 10)"),
) -> SearchSuggestionsResponse:
    clean_q = q.strip() if q else ""
    suggestions = await SearchService.get_suggestions(q=clean_q, limit=limit)
    data_payload = SearchSuggestionsResponseData(
        query=clean_q,
        suggestions=suggestions,
    )
    return SearchSuggestionsResponse(
        success=True,
        message="Search suggestions fetched successfully.",
        query=clean_q,
        suggestions=suggestions,
        data=data_payload,
    )


@router.get(
    "/trending",
    response_model=ApiResponse[List[TrendingSearchItem]],
    summary="Trending searches",
    description="Returns popular search queries aggregated from genuine search events over a configurable time window (default 7 days).",
)
async def get_trending(
    limit: int = Query(10, ge=1, le=20, description="Maximum trending terms to return (default 10, max 20)"),
    days: int = Query(7, ge=1, le=30, description="Time window in days (default 7)"),
) -> ApiResponse[List[TrendingSearchItem]]:
    trending = await SearchService.get_trending(limit=limit, days=days)
    return ApiResponse(
        success=True,
        message="Trending searches fetched successfully.",
        data=trending,
    )
