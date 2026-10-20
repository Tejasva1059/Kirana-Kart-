from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LocationCoordinates(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "latitude": 22.5,
                "longitude": 75.9,
            }
        },
    )

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")


class ServiceabilityCheckRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "postalCode": "453115",
                "city": "Indore",
                "locality": "Khudel",
                "location": {
                    "latitude": 22.7,
                    "longitude": 75.9,
                },
            }
        },
    )

    addressId: Optional[str] = Field(None, description="Saved address ID to check")
    location: Optional[LocationCoordinates] = Field(None, description="Specific coordinates to check")
    postalCode: Optional[str] = Field(None, min_length=6, max_length=6, description="6-digit Indian PIN code")
    city: Optional[str] = Field(None, max_length=100)
    locality: Optional[str] = Field(None, max_length=100)

    @field_validator("postalCode")
    @classmethod
    def validate_pincode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not (cleaned.isdigit() and len(cleaned) == 6):
                raise ValueError("Postal code must be a valid 6-digit Indian PIN code.")
            return cleaned
        return None

    @model_validator(mode="after")
    def validate_any_criteria_provided(self) -> "ServiceabilityCheckRequest":
        if not self.addressId and not self.location and not self.postalCode and not self.locality:
            raise ValueError(
                "Must provide at least one search criterion: addressId, location (latitude/longitude), or postalCode/locality."
            )
        return self


class ServiceabilityResponseData(BaseModel):
    isServiceable: bool
    serviceAreaId: Optional[str] = None
    deliveryCharge: Optional[int] = None
    currency: str = "INR"
    reasonCode: str
    estimatedDeliveryMinutes: Optional[int] = None
