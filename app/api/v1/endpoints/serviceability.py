from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, status
from app.dependencies.authentication import get_current_customer
from app.schemas.common import ApiResponse
from app.schemas.serviceability import (
    ServiceabilityCheckRequest,
    ServiceabilityResponseData,
)
from app.services.address_service import AddressService
from app.services.serviceability_service import ServiceabilityService

router = APIRouter(prefix="/serviceability", tags=["Delivery Serviceability"])


@router.post(
    "/check",
    response_model=ApiResponse[ServiceabilityResponseData],
    status_code=status.HTTP_200_OK,
    summary="Check delivery eligibility",
    description="Evaluates whether delivery is available for a saved customer address, coordinate point, or location/PIN code input.",
)
async def check_serviceability(
    payload: ServiceabilityCheckRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[ServiceabilityResponseData]:
    customer_id = str(current_customer["_id"])
    postal_code = payload.postalCode
    city = payload.city
    locality = payload.locality
    coordinates: Optional[List[float]] = None

    if payload.location:
        coordinates = [payload.location.longitude, payload.location.latitude]

    # If addressId is provided, retrieve verified address details with customer ownership validation
    if payload.addressId:
        addr = await AddressService.get_address(customer_id=customer_id, address_id=payload.addressId)
        postal_code = addr.postalCode
        city = addr.city
        locality = addr.locality
        if addr.location and addr.location.coordinates:
            coordinates = addr.location.coordinates

    result = await ServiceabilityService.check_serviceability(
        postal_code=postal_code,
        city=city,
        locality=locality,
        coordinates=coordinates,
    )

    message = (
        "Delivery is available at this location."
        if result.isServiceable
        else "Delivery is not currently available at this location."
    )

    return ApiResponse[ServiceabilityResponseData](
        success=True,
        message=message,
        data=result,
    )
