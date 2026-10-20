from typing import List, Optional
from fastapi import APIRouter, Path, Query
from app.schemas.common import ApiResponse
from app.schemas.product import (
    PaginationMeta,
    ProductAvailabilityResponseData,
    ProductDetailResponseData,
    ProductListItem,
    ProductListResponseData,
)
from app.schemas.variant import ProductVariantItem, VariantListResponseData
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "",
    response_model=ApiResponse[ProductListResponseData],
    summary="Browse, filter, and paginate products",
    description="Searches and filters the product catalogue with deterministic sorting, optional shop pricing, and stock filtering.",
)
async def list_products(
    q: Optional[str] = Query(None, description="Search keyword across product name, brand, keywords"),
    categoryId: Optional[str] = Query(None, description="Filter by parent category"),
    subcategoryId: Optional[str] = Query(None, description="Filter by subcategory"),
    shopId: Optional[str] = Query(None, description="Selected shop identifier for price and inventory scoping"),
    serviceAreaId: Optional[str] = Query(None, description="Service area identifier to resolve eligible shops"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    minPrice: Optional[int] = Query(None, ge=0, description="Minimum price in paise"),
    maxPrice: Optional[int] = Query(None, ge=0, description="Maximum price in paise"),
    inStockOnly: bool = Query(False, description="Show only products currently in stock at selected shop"),
    featuredOnly: bool = Query(False, description="Show only featured products"),
    sort: str = Query("relevance", description="Sort order: relevance, price_asc, price_desc, name_asc, newest"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> ApiResponse[ProductListResponseData]:
    items, total = await ProductService.list_products(
        q=q,
        category_id=categoryId,
        subcategory_id=subcategoryId,
        shop_id=shopId,
        service_area_id=serviceAreaId,
        brand=brand,
        min_price=minPrice,
        max_price=maxPrice,
        in_stock_only=inStockOnly,
        featured_only=featuredOnly,
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


@router.get(
    "/{productId}",
    response_model=ApiResponse[ProductDetailResponseData],
    summary="Product details",
    description="Returns product details, active variants, and optional shop-scoped pricing and stock.",
)
async def get_product(
    productId: str = Path(..., description="Product ID"),
    shopId: Optional[str] = Query(None, description="Selected shop ID"),
    serviceAreaId: Optional[str] = Query(None, description="Delivery service area ID"),
) -> ApiResponse[ProductDetailResponseData]:
    product = await ProductService.get_product_by_id(
        product_id=productId,
        shop_id=shopId,
        service_area_id=serviceAreaId,
    )
    return ApiResponse(
        success=True,
        message="Product fetched successfully.",
        data=product,
    )


@router.get(
    "/{productId}/variants",
    response_model=ApiResponse[VariantListResponseData],
    summary="Product pack sizes and variants",
    description="Returns active variants for a product with pack sizes, units, SKUs, and shop-specific inventory when shopId is supplied.",
)
async def get_product_variants(
    productId: str = Path(..., description="Product ID"),
    shopId: Optional[str] = Query(None, description="Selected shop ID"),
    serviceAreaId: Optional[str] = Query(None, description="Delivery service area ID"),
) -> ApiResponse[VariantListResponseData]:
    variants = await ProductService.get_product_variants(
        product_id=productId,
        shop_id=shopId,
        service_area_id=serviceAreaId,
    )
    return ApiResponse(
        success=True,
        message="Product variants fetched successfully.",
        data=VariantListResponseData(items=variants),
    )


@router.get(
    "/{productId}/availability",
    response_model=ApiResponse[ProductAvailabilityResponseData],
    summary="Product availability for a selected shop or area",
    description="Evaluates purchasing availability for a product or specific variant considering shop hours, active status, and real-time stock.",
)
async def check_product_availability(
    productId: str = Path(..., description="Product ID"),
    shopId: Optional[str] = Query(None, description="Selected shop identifier"),
    serviceAreaId: Optional[str] = Query(None, description="Delivery service area identifier"),
    variantId: Optional[str] = Query(None, description="Optional variant identifier"),
) -> ApiResponse[ProductAvailabilityResponseData]:
    result = await ProductService.check_product_availability(
        product_id=productId,
        shop_id=shopId,
        service_area_id=serviceAreaId,
        variant_id=variantId,
    )
    return ApiResponse(
        success=True,
        message="Availability checked successfully.",
        data=result,
    )


@router.get(
    "/{productId}/related",
    response_model=ApiResponse[List[ProductListItem]],
    summary="Related products",
    description="Returns related active products based on shared category, subcategory, or brand, excluding the current product.",
)
async def get_related_products(
    productId: str = Path(..., description="Product ID"),
    shopId: Optional[str] = Query(None, description="Selected shop ID"),
    serviceAreaId: Optional[str] = Query(None, description="Delivery service area ID"),
    limit: int = Query(10, ge=1, le=20, description="Maximum related products to return (default 10, max 20)"),
) -> ApiResponse[List[ProductListItem]]:
    items = await ProductService.get_related_products(
        product_id=productId,
        shop_id=shopId,
        service_area_id=serviceAreaId,
        limit=limit,
    )
    return ApiResponse(
        success=True,
        message="Related products fetched successfully.",
        data=items,
    )
