from typing import List, Optional
from fastapi import APIRouter, Path, Query
from app.schemas.category import CategoryItem, CategoryListResponseData
from app.schemas.common import ApiResponse
from app.schemas.product import PaginationMeta, ProductListResponseData
from app.services.category_service import CategoryService
from app.services.product_service import ProductService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get(
    "",
    response_model=ApiResponse[CategoryListResponseData],
    summary="List categories",
    description="Returns top-level active categories sorted deterministically, with optional subcategories.",
)
async def list_categories(
    includeSubcategories: bool = Query(False, description="Whether to include active child subcategories"),
    featuredOnly: bool = Query(False, description="Filter only featured categories"),
    serviceAreaId: Optional[str] = Query(None, description="Optional service area identifier"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
) -> ApiResponse[CategoryListResponseData]:
    items, total = await CategoryService.list_categories(
        include_subcategories=includeSubcategories,
        featured_only=featuredOnly,
        service_area_id=serviceAreaId,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        success=True,
        message="Categories fetched successfully.",
        data=CategoryListResponseData(items=items, total=total, limit=limit, offset=offset),
    )


@router.get(
    "/{categoryId}",
    response_model=ApiResponse[CategoryItem],
    summary="Category details",
    description="Returns public category details by ID. Returns 404 if inactive or not found.",
)
async def get_category(
    categoryId: str = Path(..., description="Category ID (24-char hex or slug)"),
) -> ApiResponse[CategoryItem]:
    cat = await CategoryService.get_category_by_id(categoryId)
    return ApiResponse(
        success=True,
        message="Category fetched successfully.",
        data=cat,
    )


@router.get(
    "/{categoryId}/subcategories",
    response_model=ApiResponse[List[CategoryItem]],
    summary="List subcategories",
    description="Returns active subcategories of the specified parent category.",
)
async def list_subcategories(
    categoryId: str = Path(..., description="Parent category ID"),
) -> ApiResponse[List[CategoryItem]]:
    subs = await CategoryService.list_subcategories(categoryId)
    return ApiResponse(
        success=True,
        message="Subcategories fetched successfully.",
        data=subs,
    )


@router.get(
    "/{categoryId}/products",
    response_model=ApiResponse[ProductListResponseData],
    summary="List category products",
    description="Returns active products belonging to the category, with optional shop-scoped pricing and inventory.",
)
async def list_category_products(
    categoryId: str = Path(..., description="Category ID"),
    shopId: Optional[str] = Query(None, description="Selected shop identifier"),
    serviceAreaId: Optional[str] = Query(None, description="Delivery service area identifier"),
    variantId: Optional[str] = Query(None, description="Filter for specific variant"),
    inStockOnly: bool = Query(False, description="Filter only products with positive stock at selected shop"),
    sort: str = Query("relevance", description="Sorting order (relevance, price_asc, price_desc, name_asc, newest)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> ApiResponse[ProductListResponseData]:
    # Ensure category exists
    await CategoryService.get_category_by_id(categoryId)

    items, total = await ProductService.list_products(
        category_id=categoryId,
        shop_id=shopId,
        service_area_id=serviceAreaId,
        in_stock_only=inStockOnly,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    has_more = (offset + limit) < total
    return ApiResponse(
        success=True,
        message="Products fetched successfully.",
        data=ProductListResponseData(
            items=items,
            pagination=PaginationMeta(total=total, limit=limit, offset=offset, hasMore=has_more),
        ),
    )
