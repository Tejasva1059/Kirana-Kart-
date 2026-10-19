from typing import Any, Dict
from fastapi import APIRouter, Depends, Request, status
from app.core.exceptions import BadRequestException
from app.dependencies.authentication import get_current_customer
from app.schemas.common import ApiResponse
from app.schemas.customer import (
    CustomerProfileUpdateRequest,
    CustomerPublicProfile,
)
from app.services.customer_service import CustomerService

router = APIRouter(prefix="/customers", tags=["Customer Profile"])


@router.patch(
    "/me",
    response_model=ApiResponse[Dict[str, CustomerPublicProfile]],
    status_code=status.HTTP_200_OK,
    summary="Update authenticated customer profile",
    description="Updates approved profile fields (fullName, email) for the authenticated customer. Changes to mobile number are strictly forbidden here.",
)
async def update_my_profile(
    payload: CustomerProfileUpdateRequest,
    raw_request: Request,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[Dict[str, CustomerPublicProfile]]:
    # Explicitly check for forbidden mobileNumber modification attempts
    try:
        body = await raw_request.json()
        if "mobileNumber" in body or "mobile_number" in body:
            raise BadRequestException(
                "Mobile number cannot be updated via this endpoint. Changing your mobile number requires separate OTP verification.",
                code="MOBILE_UPDATE_FORBIDDEN",
            )
        for forbidden_key in ["role", "status", "_id", "id", "password", "mobileVerified", "emailVerified", "acceptedTerms"]:
            if forbidden_key in body:
                raise BadRequestException(
                    f"Modification of protected field '{forbidden_key}' is strictly forbidden.",
                    code="PROTECTED_FIELD_MODIFICATION",
                )
    except BadRequestException:
        raise
    except Exception:
        pass

    customer_id = str(current_customer["_id"])
    updated_profile = await CustomerService.update_profile(
        customer_id=customer_id,
        full_name=payload.fullName,
        email=payload.email,
    )

    return ApiResponse[Dict[str, CustomerPublicProfile]](
        success=True,
        message="Customer profile updated successfully.",
        data={"customer": updated_profile},
    )
