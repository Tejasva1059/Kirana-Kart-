from typing import Any, Dict
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_access_token
from app.services.customer_service import CustomerService
from app.services.token_service import TokenService

security_scheme = HTTPBearer(auto_error=False)


async def get_current_customer(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> Dict[str, Any]:
    """
    Authenticate request via JWT Bearer access token.
    Validates token signature, claims, expiry, active session status, and active customer account.
    """
    if not credentials or not credentials.credentials:
        raise UnauthorizedException(
            "Authentication credentials were not provided in Authorization header.",
            code="NOT_AUTHENTICATED",
        )

    token = credentials.credentials
    payload = decode_access_token(token)

    customer_id = payload.get("sub")
    session_id = payload.get("sid")

    if not customer_id or not session_id:
        raise UnauthorizedException("Invalid token claims.", code="INVALID_TOKEN_CLAIMS")

    # Verify session is still valid and not revoked
    is_active = await TokenService.is_session_active(session_id=session_id, customer_id=customer_id)
    if not is_active:
        raise UnauthorizedException("Session has been revoked or expired.", code="SESSION_REVOKED")

    # Fetch and verify active customer
    customer = await CustomerService.get_customer_by_id(customer_id)
    if not customer:
        raise UnauthorizedException("Customer account not found.", code="CUSTOMER_NOT_FOUND")

    if customer.get("status") != "active":
        raise UnauthorizedException("Customer account is blocked or inactive.", code="ACCOUNT_INACTIVE")

    # Attach session id to customer context
    customer["_sessionId"] = session_id
    return customer
