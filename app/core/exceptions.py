from typing import Any, List, Optional
from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        message: str,
        code: str = "ERROR",
        details: Optional[List[Any]] = None,
    ):
        super().__init__(status_code=status_code, detail=message)
        self.status_code = status_code
        self.message = message
        self.code = code
        self.details = details or []


class BadRequestException(AppException):
    def __init__(self, message: str, code: str = "BAD_REQUEST", details: Optional[List[Any]] = None):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, message=message, code=code, details=details)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Invalid or expired authentication credentials", code: str = "UNAUTHORIZED", details: Optional[List[Any]] = None):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, message=message, code=code, details=details)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Operation not permitted", code: str = "FORBIDDEN", details: Optional[List[Any]] = None):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, message=message, code=code, details=details)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND", details: Optional[List[Any]] = None):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, message=message, code=code, details=details)


class ConflictException(AppException):
    def __init__(self, message: str, code: str = "CONFLICT", details: Optional[List[Any]] = None):
        super().__init__(status_code=status.HTTP_409_CONFLICT, message=message, code=code, details=details)


class RateLimitExceededException(AppException):
    def __init__(self, message: str = "Rate limit exceeded. Please try again later.", code: str = "RATE_LIMIT_EXCEEDED", retry_after: int = 60):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            message=message,
            code=code,
            details=[{"retryAfterSeconds": retry_after}],
        )
        self.retry_after = retry_after


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service temporarily unavailable", code: str = "SERVICE_UNAVAILABLE", details: Optional[List[Any]] = None):
        super().__init__(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, message=message, code=code, details=details)
