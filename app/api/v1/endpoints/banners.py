from typing import Optional
from fastapi import APIRouter, Query
from app.schemas.banner import BannerListResponseData
from app.schemas.common import ApiResponse
from app.services.banner_service import BannerService

router = APIRouter(prefix="/banners", tags=["Banners"])


@router.get(
    "",
    response_model=ApiResponse[BannerListResponseData],
    summary="Load home banners",
    description="Returns active and scheduled promotional banners, optionally filtered by service area.",
)
async def get_banners(
    serviceAreaId: Optional[str] = Query(None, description="Optional service area identifier"),
    limit: int = Query(10, ge=1, le=20, description="Maximum banners to return (default 10, max 20)"),
) -> ApiResponse[BannerListResponseData]:
    banners = await BannerService.list_banners(service_area_id=serviceAreaId, limit=limit)
    return ApiResponse(
        success=True,
        message="Banners fetched successfully.",
        data=BannerListResponseData(items=banners),
    )
