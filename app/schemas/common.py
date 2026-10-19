from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetails(BaseModel):
    code: str
    details: List[Any] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    success: bool = False
    message: str = "Request could not be completed."
    error: ErrorDetails


class ApiResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    success: bool = True
    message: str = "Operation completed successfully."
    data: Optional[T] = None
