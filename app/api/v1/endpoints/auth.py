from typing import Any, Dict
from fastapi import APIRouter, Depends, Request, status
from app.core.exceptions import BadRequestException
from app.dependencies.authentication import get_current_customer
from app.dependencies.rate_limit import get_client_ip, rate_limit_by_ip
from app.schemas.auth import (
    AuthResponseData,
    CustomerLoginRequest,
    CustomerSignupRequest,
    LogoutRequest,
    OTPRequest,
    OTPRequestData,
    OTPVerifyData,
    OTPVerifyRequest,
    TokenData,
    TokenRefreshRequest,
)
from app.schemas.common import ApiResponse
from app.schemas.customer import CustomerPublicProfile
from app.services.auth_service import AuthService
from app.services.customer_service import CustomerService
from app.services.otp_service import OTPService
from app.services.token_service import TokenService

router = APIRouter(prefix="/auth", tags=["Customer Authentication"])


@router.post(
    "/otp/request",
    response_model=ApiResponse[OTPRequestData],
    status_code=status.HTTP_200_OK,
    summary="Request signup or login OTP",
    description="Validates mobile number and issues a secure 6-digit OTP challenge via SMS. Prevents account enumeration.",
    dependencies=[Depends(rate_limit_by_ip(max_requests=10, window_seconds=60, prefix="otp_req"))],
)
async def request_otp(payload: OTPRequest, request: Request) -> ApiResponse[OTPRequestData]:
    client_ip = get_client_ip(request)
    data = await OTPService.request_otp(
        mobile_number=payload.mobileNumber,
        purpose=payload.purpose,
        client_ip=client_ip,
    )
    msg = f"OTP sent successfully. [Testing Mode OTP: {data.mockOtp}]" if data.mockOtp else "If eligible, an OTP has been sent."
    return ApiResponse[OTPRequestData](
        success=True,
        message=msg,
        data=data,
    )


@router.post(
    "/otp/verify",
    response_model=ApiResponse[OTPVerifyData],
    status_code=status.HTTP_200_OK,
    summary="Verify OTP challenge",
    description="Verifies the submitted OTP against cryptographic HMAC and issues an opaque, single-use verification ticket.",
    dependencies=[Depends(rate_limit_by_ip(max_requests=15, window_seconds=60, prefix="otp_ver"))],
)
async def verify_otp(payload: OTPVerifyRequest) -> ApiResponse[OTPVerifyData]:
    data = await OTPService.verify_otp(
        mobile_number=payload.mobileNumber,
        otp=payload.otp,
        purpose=payload.purpose,
        challenge_id=payload.challengeId,
    )
    return ApiResponse[OTPVerifyData](
        success=True,
        message="OTP verified successfully.",
        data=data,
    )


@router.post(
    "/customer/signup",
    response_model=ApiResponse[AuthResponseData],
    status_code=status.HTTP_201_CREATED,
    summary="Register customer with verified ticket",
    description="Creates a new customer account using an unconsumed verification ticket, assigns the customer role, and establishes an authenticated session.",
    dependencies=[Depends(rate_limit_by_ip(max_requests=10, window_seconds=60, prefix="signup"))],
)
async def signup_customer(payload: CustomerSignupRequest, request: Request) -> ApiResponse[AuthResponseData]:
    client_ip = get_client_ip(request)
    data = await AuthService.signup_customer(
        request=payload,
        ip_address_hash=client_ip,
    )
    return ApiResponse[AuthResponseData](
        success=True,
        message="Customer registered successfully.",
        data=data,
    )


@router.post(
    "/customer/login",
    response_model=ApiResponse[AuthResponseData],
    status_code=status.HTTP_200_OK,
    summary="Login customer with verified ticket",
    description="Authenticates an existing active customer using an unconsumed login verification ticket and creates a new session.",
    dependencies=[Depends(rate_limit_by_ip(max_requests=15, window_seconds=60, prefix="login"))],
)
async def login_customer(payload: CustomerLoginRequest, request: Request) -> ApiResponse[AuthResponseData]:
    client_ip = get_client_ip(request)
    data = await AuthService.login_customer(
        request=payload,
        ip_address_hash=client_ip,
    )
    return ApiResponse[AuthResponseData](
        success=True,
        message="Customer logged in successfully.",
        data=data,
    )


@router.post(
    "/token/refresh",
    response_model=ApiResponse[TokenData],
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
    description="Atomically rotates the opaque refresh token, checks for token reuse attacks, and issues a new JWT access token.",
    dependencies=[Depends(rate_limit_by_ip(max_requests=30, window_seconds=60, prefix="refresh"))],
)
@router.post(
    "/refresh",
    response_model=ApiResponse[TokenData],
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token (alias)",
    description="Alias for /token/refresh for client backward compatibility.",
    include_in_schema=False,
    dependencies=[Depends(rate_limit_by_ip(max_requests=30, window_seconds=60, prefix="refresh"))],
)
async def refresh_tokens(payload: TokenRefreshRequest) -> ApiResponse[TokenData]:
    tokens = await TokenService.rotate_refresh_token(raw_refresh_token=payload.refreshToken)
    return ApiResponse[TokenData](
        success=True,
        message="Tokens refreshed successfully",
        data=tokens,
    )


@router.post(
    "/logout",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Revoke current session",
    description="Revokes the authenticated customer's session and invalidates the associated refresh token.",
)
async def logout(
    payload: LogoutRequest,
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[Dict[str, Any]]:
    session_id = current_customer.get("_sessionId")
    customer_id = str(current_customer["_id"])
    await TokenService.revoke_session(
        raw_refresh_token=payload.refreshToken,
        customer_id=customer_id,
        session_id=session_id,
    )
    return ApiResponse[Dict[str, Any]](
        success=True,
        message="Logged out successfully.",
        data={},
    )


@router.get(
    "/me",
    response_model=ApiResponse[Dict[str, CustomerPublicProfile]],
    status_code=status.HTTP_200_OK,
    summary="Get authenticated customer profile",
    description="Returns the profile information of the currently authenticated customer.",
)
async def get_my_profile(
    current_customer: Dict[str, Any] = Depends(get_current_customer),
) -> ApiResponse[Dict[str, CustomerPublicProfile]]:
    profile = CustomerService.map_to_public_profile(current_customer)
    return ApiResponse[Dict[str, CustomerPublicProfile]](
        success=True,
        message="Profile fetched successfully.",
        data={"customer": profile},
    )
