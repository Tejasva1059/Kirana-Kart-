from typing import Callable
from fastapi import Request
from app.core.rate_limiter import enforce_rate_limit


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def rate_limit_by_ip(max_requests: int, window_seconds: int, prefix: str = "ip") -> Callable:
    async def dependency(request: Request) -> None:
        ip = get_client_ip(request)
        key = f"{prefix}:{ip}"
        await enforce_rate_limit(
            key=key,
            max_requests=max_requests,
            window_seconds=window_seconds,
            message=f"Too many requests from this IP. Please wait before retrying.",
        )

    return dependency
