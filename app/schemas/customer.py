from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CustomerPublicProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    fullName: str
    email: Optional[str] = None
    mobileNumber: str
    role: str
    status: str
    createdAt: Optional[datetime] = None


class CustomerProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "fullName": "Tejas Sharma",
                "email": "tejas@example.com",
            }
        },
    )

    fullName: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[str] = None

    @field_validator("fullName")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 2 or len(v) > 100:
                raise ValueError("Full name must be between 2 and 100 characters.")
        return v

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "CustomerProfileUpdateRequest":
        if self.fullName is None and self.email is None:
            raise ValueError("At least one profile field (fullName or email) must be provided for update.")
        return self
