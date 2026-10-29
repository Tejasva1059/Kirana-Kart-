from typing import Any, Dict
from fastapi import APIRouter, Depends, Path, status

from app.dependencies.authentication import get_current_customer
from app.schemas.cart import (
    CartItemAddRequest,
    CartItemUpdateRequest,
    CartResponseData,
    CartValidationResponseData,
    GuestCartMergeRequest,
    GuestCartMergeResponseData,
)
from app.schemas.common import ApiResponse
from app.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get(
    "",
    response_model=ApiResponse[CartResponseData],
    status_code=status.HTTP_200_OK,
    summary="Fetch the current user's cart",
    description="Fetches the authenticated customer's current cart with real-time catalogue prices, subtotal, and stock warnings.",
)
async def get_cart(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[CartResponseData]:
    customer_id = str(current_customer["_id"])
    cart_data = await CartService.get_cart(customer_id)
    return ApiResponse[CartResponseData](
        success=True,
        message="Cart fetched successfully.",
        data=cart_data,
    )


@router.post(
    "/items",
    response_model=ApiResponse[CartResponseData],
    status_code=status.HTTP_200_OK,
    summary="Add a product variant to the cart",
    description="Adds a product variant to the customer's cart or increments quantity if already present. Checks server-side inventory and prices.",
)
async def add_item_to_cart(
    payload: CartItemAddRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[CartResponseData]:
    customer_id = str(current_customer["_id"])
    cart_data = await CartService.add_item(
        customer_id=customer_id,
        product_id=payload.productId,
        variant_id=payload.variantId,
        quantity=payload.quantity,
        shop_id=payload.shopId,
    )
    return ApiResponse[CartResponseData](
        success=True,
        message="Item added to cart successfully.",
        data=cart_data,
    )


@router.patch(
    "/items/{itemId}",
    response_model=ApiResponse[CartResponseData],
    status_code=status.HTTP_200_OK,
    summary="Change cart item quantity",
    description="Updates the quantity of a specific item in the authenticated customer's cart. Re-evaluates stock limits.",
)
async def update_cart_item_quantity(
    payload: CartItemUpdateRequest,
    itemId: str = Path(..., description="Unique cart item ID"),
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[CartResponseData]:
    customer_id = str(current_customer["_id"])
    cart_data = await CartService.update_item_quantity(
        customer_id=customer_id,
        item_id=itemId,
        quantity=payload.quantity,
    )
    return ApiResponse[CartResponseData](
        success=True,
        message="Cart item quantity updated successfully.",
        data=cart_data,
    )


@router.delete(
    "/items/{itemId}",
    response_model=ApiResponse[CartResponseData],
    status_code=status.HTTP_200_OK,
    summary="Remove a cart item",
    description="Removes a specific item from the authenticated customer's cart and recalculates subtotals.",
)
async def remove_cart_item(
    itemId: str = Path(..., description="Unique cart item ID to remove"),
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[CartResponseData]:
    customer_id = str(current_customer["_id"])
    cart_data = await CartService.remove_item(
        customer_id=customer_id,
        item_id=itemId,
    )
    return ApiResponse[CartResponseData](
        success=True,
        message="Item removed from cart successfully.",
        data=cart_data,
    )


@router.delete(
    "/items",
    response_model=ApiResponse[CartResponseData],
    status_code=status.HTTP_200_OK,
    summary="Clear the cart",
    description="Removes all items from the authenticated customer's cart and resets totals to zero.",
)
async def clear_cart(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[CartResponseData]:
    customer_id = str(current_customer["_id"])
    cart_data = await CartService.clear_cart(customer_id)
    return ApiResponse[CartResponseData](
        success=True,
        message="Cart cleared successfully.",
        data=cart_data,
    )


@router.post(
    "/validate",
    response_model=ApiResponse[CartValidationResponseData],
    status_code=status.HTTP_200_OK,
    summary="Revalidate stock and prices",
    description="Pre-checkout revalidation of all cart items. Authoritatively verifies inventory availability, deactivations, and price fluctuations without reserving stock.",
)
async def validate_cart(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[CartValidationResponseData]:
    customer_id = str(current_customer["_id"])
    validation_data = await CartService.validate_cart(customer_id)
    return ApiResponse[CartValidationResponseData](
        success=True,
        message="Cart validated successfully.",
        data=validation_data,
    )


@router.post(
    "/merge",
    response_model=ApiResponse[GuestCartMergeResponseData],
    status_code=status.HTTP_200_OK,
    summary="Merge guest cart after login",
    description="Transfers items from an unauthenticated guest cart into the customer's cart after authentication. Idempotently invalidates the guest cart.",
)
async def merge_guest_cart(
    payload: GuestCartMergeRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[GuestCartMergeResponseData]:
    customer_id = str(current_customer["_id"])
    merge_data = await CartService.merge_guest_cart(
        customer_id=customer_id,
        guest_cart_id=payload.guestCartId,
    )
    return ApiResponse[GuestCartMergeResponseData](
        success=True,
        message="Guest cart merged successfully.",
        data=merge_data,
    )
