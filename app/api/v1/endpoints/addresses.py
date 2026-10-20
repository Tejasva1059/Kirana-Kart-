from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, status
from app.dependencies.authentication import get_current_customer
from app.schemas.address import (
    AddressCreatedResponseData,
    AddressCreateRequest,
    AddressDeleteResponseData,
    AddressListResponseData,
    AddressResponse,
    AddressUpdateRequest,
    DefaultAddressResponseData,
)
from app.schemas.common import ApiResponse
from app.services.address_service import AddressService

router = APIRouter(prefix="/addresses", tags=["Customer Addresses"])


@router.get(
    "",
    response_model=ApiResponse[AddressListResponseData],
    status_code=status.HTTP_200_OK,
    summary="List saved customer addresses",
    description="Retrieves all saved addresses for the authenticated customer. The default address is returned first, followed by the most recently updated.",
)
async def list_addresses(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of addresses to return"),
    offset: int = Query(0, ge=0, description="Number of addresses to skip"),
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[AddressListResponseData]:
    customer_id = str(current_customer["_id"])
    data = await AddressService.list_addresses(customer_id=customer_id, limit=limit, offset=offset)
    return ApiResponse[AddressListResponseData](
        success=True,
        message="Addresses fetched successfully.",
        data=data,
    )


@router.post(
    "",
    response_model=ApiResponse[AddressCreatedResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new address",
    description="Saves a new customer address, geocodes coordinates if missing, applies default rules, and evaluates delivery serviceability.",
)
async def create_address(
    payload: AddressCreateRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[AddressCreatedResponseData]:
    customer_id = str(current_customer["_id"])
    data = await AddressService.create_address(customer_id=customer_id, payload=payload)
    return ApiResponse[AddressCreatedResponseData](
        success=True,
        message="Address saved successfully.",
        data=data,
    )


@router.get(
    "/{addressId}",
    response_model=ApiResponse[AddressResponse],
    status_code=status.HTTP_200_OK,
    summary="Fetch address by ID",
    description="Returns complete details and latest serviceability status for an address owned by the authenticated customer.",
)
async def get_address(
    addressId: str,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[AddressResponse]:
    customer_id = str(current_customer["_id"])
    data = await AddressService.get_address(customer_id=customer_id, address_id=addressId)
    return ApiResponse[AddressResponse](
        success=True,
        message="Address fetched successfully.",
        data=data,
    )


@router.patch(
    "/{addressId}",
    response_model=ApiResponse[AddressResponse],
    status_code=status.HTTP_200_OK,
    summary="Edit saved address",
    description="Updates permitted fields on an address owned by the authenticated customer. Re-evaluates geocoding and serviceability when necessary.",
)
async def update_address(
    addressId: str,
    payload: AddressUpdateRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[AddressResponse]:
    customer_id = str(current_customer["_id"])
    data = await AddressService.update_address(
        customer_id=customer_id,
        address_id=addressId,
        payload=payload,
    )
    return ApiResponse[AddressResponse](
        success=True,
        message="Address updated successfully.",
        data=data,
    )


@router.delete(
    "/{addressId}",
    response_model=ApiResponse[AddressDeleteResponseData],
    status_code=status.HTTP_200_OK,
    summary="Delete saved address",
    description="Deletes an address owned by the authenticated customer. If the deleted address was default, reassigns default to the most recently updated remaining address.",
)
async def delete_address(
    addressId: str,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[AddressDeleteResponseData]:
    customer_id = str(current_customer["_id"])
    data = await AddressService.delete_address(customer_id=customer_id, address_id=addressId)
    return ApiResponse[AddressDeleteResponseData](
        success=True,
        message="Address deleted successfully.",
        data=data,
    )


@router.patch(
    "/{addressId}/default",
    response_model=ApiResponse[DefaultAddressResponseData],
    status_code=status.HTTP_200_OK,
    summary="Set address as default",
    description="Atomically designates the specified address as the customer's primary default address and unsets any previous default.",
)
async def set_default_address(
    addressId: str,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[DefaultAddressResponseData]:
    customer_id = str(current_customer["_id"])
    data = await AddressService.set_default_address(customer_id=customer_id, address_id=addressId)
    return ApiResponse[DefaultAddressResponseData](
        success=True,
        message="Default address updated successfully.",
        data=data,
    )
