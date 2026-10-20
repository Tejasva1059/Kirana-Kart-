from typing import Optional
from fastapi import APIRouter, Path, Query
from app.schemas.common import ApiResponse
from app.schemas.product import PaginationMeta, ProductListResponseData
from app.schemas.shop import (
    ShopAvailabilityResponseData,
    ShopDetailResponseData,
    ShopListResponseData,
)
from app.services.product_service import ProductService
from app.services.shop_service import ShopService

router = APIRouter(prefix="/shops", tags=["Shops"])


@router.get(
    "",
    response_model=ApiResponse[ShopListResponseData],
    summary="Find available shops",
    description="Discovers active shops based on delivery service area, GPS coordinates, postal code, or operating hours.",
)
async def list_shops(
    latitude: Optional[float] = Query(None, description="GPS latitude"),
    longitude: Optional[float] = Query(None, description="GPS longitude"),
    postalCode: Optional[str] = Query(None, description="Delivery postal code"),
    serviceAreaId: Optional[str] = Query(None, description="Service area identifier"),
    categoryId: Optional[str] = Query(None, description="Filter shops carrying products in this category"),
    openNow: Optional[bool] = Query(None, description="Filter shops currently open based on operating hours"),
    acceptsOrders: Optional[bool] = Query(None, description="Filter shops currently accepting orders"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> ApiResponse[ShopListResponseData]:
    items, total = await ShopService.list_shops(
        latitude=latitude,
        longitude=longitude,
        postal_code=postalCode,
        service_area_id=serviceAreaId,
        category_id=categoryId,
        open_now=openNow,
        accepts_orders=acceptsOrders,
        limit=limit,
        offset=offset,
    )
    has_more = (offset + limit) < total
    return ApiResponse(
        success=True,
        message="Shops fetched successfully.",
        data=ShopListResponseData(
            items=items,
            pagination=PaginationMeta(total=total, limit=limit, offset=offset, hasMore=has_more),
        ),
    )


@router.get(
    "/{shopId}",
    response_model=ApiResponse[ShopDetailResponseData],
    summary="Shop details",
    description="Returns public shop details, address, opening hours, and real-time open/closed status.",
)
async def get_shop(
    shopId: str = Path(..., description="Shop ID"),
) -> ApiResponse[ShopDetailResponseData]:
    shop = await ShopService.get_shop_by_id(shopId)
    return ApiResponse(
        success=True,
        message="Shop fetched successfully.",
        data=shop,
    )


@router.get(
    "/{shopId}/products",
    response_model=ApiResponse[ProductListResponseData],
    summary="Shop catalogue",
    description="Authoritative catalogue scoped to the selected shop with shop-specific prices, stock, and filtering.",
)
async def get_shop_products(
    shopId: str = Path(..., description="Shop ID"),
    categoryId: Optional[str] = Query(None, description="Filter by category"),
    subcategoryId: Optional[str] = Query(None, description="Filter by subcategory"),
    q: Optional[str] = Query(None, description="Search query"),
    brand: Optional[str] = Query(None, description="Filter by brand"),
    minPrice: Optional[int] = Query(None, ge=0, description="Minimum price in paise"),
    maxPrice: Optional[int] = Query(None, ge=0, description="Maximum price in paise"),
    inStockOnly: bool = Query(False, description="Filter only products with positive stock at this shop"),
    sort: str = Query("relevance", description="Sort order: relevance, price_asc, price_desc, name_asc, newest"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> ApiResponse[ProductListResponseData]:
    # Verify shop exists
    await ShopService.get_shop_by_id(shopId)

    items, total = await ProductService.list_products(
        q=q,
        category_id=categoryId,
        subcategory_id=subcategoryId,
        shop_id=shopId,
        brand=brand,
        min_price=minPrice,
        max_price=maxPrice,
        in_stock_only=inStockOnly,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    has_more = (offset + limit) < total
    return ApiResponse(
        success=True,
        message="Shop products fetched successfully.",
        data=ProductListResponseData(
            items=items,
            pagination=PaginationMeta(total=total, limit=limit, offset=offset, hasMore=has_more),
        ),
    )


@router.get(
    "/{shopId}/availability",
    response_model=ApiResponse[ShopAvailabilityResponseData],
    summary="Shop hours and ordering availability",
    description="Calculates shop operating hours, open status, and order acceptance in the shop's timezone.",
)
async def get_shop_availability(
    shopId: str = Path(..., description="Shop ID"),
    serviceAreaId: Optional[str] = Query(None, description="Optional service area identifier to test delivery eligibility"),
) -> ApiResponse[ShopAvailabilityResponseData]:
    availability = await ShopService.get_shop_availability(
        shop_id=shopId,
        service_area_id=serviceAreaId,
    )
    return ApiResponse(
        success=True,
        message="Shop availability fetched successfully.",
        data=availability,
    )
