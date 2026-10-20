from typing import Optional
from fastapi import APIRouter, Query, status
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.schemas.common import ApiResponse
from app.schemas.location import LocationSearchResponseData
from app.services.geocoding_service import get_geocoding_provider
from app.services.serviceability_service import ServiceabilityService

router = APIRouter(prefix="/locations", tags=["Location Search"])


@router.get(
    "/search",
    response_model=ApiResponse[LocationSearchResponseData],
    status_code=status.HTTP_200_OK,
    summary="Search locations and addresses",
    description="Autocomplete and place search using the configured geocoding provider. Cross-references results against active delivery service areas.",
)
async def search_locations(
    q: str = Query(..., min_length=1, max_length=100, description="Search query text"),
    limit: int = Query(10, ge=1, le=20, description="Maximum number of search results (1-20)"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="User's optional current latitude"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="User's optional current longitude"),
) -> ApiResponse[LocationSearchResponseData]:
    cleaned_query = q.strip()
    if len(cleaned_query) < settings.LOCATION_SEARCH_MIN_QUERY_LENGTH:
        raise BadRequestException(
            f"Search query must be at least {settings.LOCATION_SEARCH_MIN_QUERY_LENGTH} characters long.",
            code="QUERY_TOO_SHORT",
        )

    geocoder = get_geocoding_provider()
    items = await geocoder.search_places(
        query=cleaned_query,
        limit=min(limit, settings.LOCATION_SEARCH_MAX_RESULTS),
        latitude=latitude,
        longitude=longitude,
    )

    # Cross-reference results with configured service areas
    for item in items:
        coords = None
        if item.location.latitude is not None and item.location.longitude is not None:
            coords = [item.location.longitude, item.location.latitude]
        serv_res = await ServiceabilityService.check_serviceability(
            postal_code=item.postalCode,
            city=item.city,
            locality=item.locality,
            coordinates=coords,
        )
        item.isServiceable = serv_res.isServiceable

    data = LocationSearchResponseData(
        items=items,
        provider=settings.GEOCODING_PROVIDER,
    )
    return ApiResponse[LocationSearchResponseData](
        success=True,
        message="Location search completed.",
        data=data,
    )
