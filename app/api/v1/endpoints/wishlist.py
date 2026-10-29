from typing import Any, Dict
from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.authentication import get_current_customer
from app.schemas.common import ApiResponse
from app.schemas.wishlist import (
    WishlistItemAddRequest,
    WishlistItemResponse,
    WishlistResponseData,
)
from app.services.wishlist_service import WishlistService

router = APIRouter(prefix="/wishlist", tags=["Wishlist"])


@router.get(
    "",
    response_model=ApiResponse[WishlistResponseData],
    status_code=status.HTTP_200_OK,
    summary="Fetch the current user's wishlist",
    description="Fetches saved wishlist products for the authenticated customer with live pricing and availability status.",
)
async def get_wishlist(
    limit: int = Query(20, ge=1, le=100, description="Number of wishlist items to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[WishlistResponseData]:
    customer_id = str(current_customer["_id"])
    wishlist_data = await WishlistService.get_wishlist(
        customer_id=customer_id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse[WishlistResponseData](
        success=True,
        message="Wishlist fetched successfully.",
        data=wishlist_data,
    )


@router.post(
    "/items",
    response_model=ApiResponse[WishlistItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Add an item to the wishlist",
    description="Adds a product to the authenticated customer's wishlist idempotently. Stock availability is not required for wishlist addition.",
)
async def add_wishlist_item(
    payload: WishlistItemAddRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[WishlistItemResponse]:
    customer_id = str(current_customer["_id"])
    item_data = await WishlistService.add_item(
        customer_id=customer_id,
        product_id=payload.productId,
    )
    return ApiResponse[WishlistItemResponse](
        success=True,
        message="Item added to wishlist successfully.",
        data=item_data,
    )


@router.delete(
    "/items/{productId}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Remove an item from the wishlist",
    description="Removes a product from the authenticated customer's wishlist idempotently.",
)
async def remove_wishlist_item(
    productId: str = Path(..., description="Unique product ID to remove"),
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[Dict[str, Any]]:
    customer_id = str(current_customer["_id"])
    await WishlistService.remove_item(
        customer_id=customer_id,
        product_id=productId,
    )
    return ApiResponse[Dict[str, Any]](
        success=True,
        message="Item removed from wishlist successfully.",
        data={"productId": productId, "removed": True},
    )
