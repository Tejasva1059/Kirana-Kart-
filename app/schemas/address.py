from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GeoJSONPointSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "type": "Point",
                "coordinates": [75.9, 22.5],
            }
        },
    )

    type: Literal["Point"] = "Point"
    coordinates: List[float] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Coordinates ordered as [longitude, latitude]",
    )

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, v: List[float]) -> List[float]:
        lon, lat = v[0], v[1]
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Longitude {lon} out of range [-180, 180]")
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude {lat} out of range [-90, 90]")
        return [float(lon), float(lat)]


class AddressCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "label": "Home",
                "recipientName": "Rahul Sharma",
                "recipientMobile": "9876543210",
                "addressLine1": "House 12",
                "addressLine2": "Near Main Road",
                "landmark": "Near Ganesh Temple",
                "locality": "Khudel",
                "subLocality": "",
                "city": "Indore",
                "district": "Indore",
                "state": "Madhya Pradesh",
                "postalCode": "453115",
                "country": "India",
                "deliveryInstructions": "Call on arrival",
                "location": {
                    "type": "Point",
                    "coordinates": [75.9, 22.5],
                },
                "isDefault": True,
            }
        },
    )

    label: str = Field("Home", min_length=1, max_length=50)
    recipientName: str = Field(..., min_length=2, max_length=100)
    recipientMobile: str = Field(..., min_length=10, max_length=15)
    addressLine1: str = Field(..., min_length=2, max_length=255)
    addressLine2: Optional[str] = Field(None, max_length=255)
    landmark: Optional[str] = Field(None, max_length=255)
    locality: str = Field(..., min_length=2, max_length=100)
    subLocality: Optional[str] = Field(None, max_length=100)
    city: str = Field(..., min_length=2, max_length=100)
    district: str = Field(..., min_length=2, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postalCode: str = Field(..., min_length=6, max_length=6, description="6-digit Indian PIN code")
    country: str = Field("India", min_length=2, max_length=50)
    deliveryInstructions: Optional[str] = Field(None, max_length=500)
    location: Optional[GeoJSONPointSchema] = None
    isDefault: bool = False

    @field_validator("label", "recipientName", "addressLine1", "locality", "city", "district", "state", "country")
    @classmethod
    def trim_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or whitespace.")
        return cleaned

    @field_validator("addressLine2", "landmark", "subLocality", "deliveryInstructions")
    @classmethod
    def trim_optional_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @field_validator("recipientMobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        if len(digits) == 10:
            return digits
        if len(digits) == 12 and digits.startswith("91"):
            return digits[2:]
        raise ValueError("Mobile number must be a valid 10-digit Indian phone number.")

    @field_validator("postalCode")
    @classmethod
    def validate_pincode(cls, v: str) -> str:
        cleaned = v.strip()
        if not (cleaned.isdigit() and len(cleaned) == 6):
            raise ValueError("Postal code must be a valid 6-digit Indian PIN code.")
        if cleaned.startswith("0"):
            raise ValueError("Indian PIN codes cannot begin with 0.")
        return cleaned

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        if v.strip().lower() not in ["india", "in", "ind"]:
            raise ValueError("Only delivery within India is supported.")
        return "India"


class AddressUpdateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "label": "Work",
                "addressLine1": "Office 204",
                "landmark": "Near City Center",
                "postalCode": "452001",
                "deliveryInstructions": "Deliver at reception",
            }
        },
    )

    label: Optional[str] = Field(None, min_length=1, max_length=50)
    recipientName: Optional[str] = Field(None, min_length=2, max_length=100)
    recipientMobile: Optional[str] = Field(None, min_length=10, max_length=15)
    addressLine1: Optional[str] = Field(None, min_length=2, max_length=255)
    addressLine2: Optional[str] = Field(None, max_length=255)
    landmark: Optional[str] = Field(None, max_length=255)
    locality: Optional[str] = Field(None, min_length=2, max_length=100)
    subLocality: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, min_length=2, max_length=100)
    district: Optional[str] = Field(None, min_length=2, max_length=100)
    state: Optional[str] = Field(None, min_length=2, max_length=100)
    postalCode: Optional[str] = Field(None, min_length=6, max_length=6)
    country: Optional[str] = Field(None, min_length=2, max_length=50)
    deliveryInstructions: Optional[str] = Field(None, max_length=500)
    location: Optional[GeoJSONPointSchema] = None
    isDefault: Optional[bool] = None

    @field_validator("label", "recipientName", "addressLine1", "locality", "city", "district", "state")
    @classmethod
    def trim_update_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Field cannot be blank.")
            return cleaned
        return None

    @field_validator("addressLine2", "landmark", "subLocality", "deliveryInstructions")
    @classmethod
    def trim_optional_update_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @field_validator("recipientMobile")
    @classmethod
    def validate_update_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            digits = "".join(filter(str.isdigit, v))
            if len(digits) == 10:
                return digits
            if len(digits) == 12 and digits.startswith("91"):
                return digits[2:]
            raise ValueError("Mobile number must be a valid 10-digit Indian phone number.")
        return None

    @field_validator("postalCode")
    @classmethod
    def validate_update_pincode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not (cleaned.isdigit() and len(cleaned) == 6):
                raise ValueError("Postal code must be a valid 6-digit Indian PIN code.")
            if cleaned.startswith("0"):
                raise ValueError("Indian PIN codes cannot begin with 0.")
            return cleaned
        return None

    @field_validator("country")
    @classmethod
    def validate_update_country(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if v.strip().lower() not in ["india", "in", "ind"]:
                raise ValueError("Only delivery within India is supported.")
            return "India"
        return None

    @model_validator(mode="after")
    def verify_at_least_one_field(self) -> "AddressUpdateRequest":
        non_none = [k for k, v in self.__dict__.items() if v is not None]
        if not non_none:
            raise ValueError("At least one address field must be provided for update.")
        return self


class AddressServiceabilitySummary(BaseModel):
    isServiceable: bool
    deliveryCharge: Optional[int] = 0
    currency: str = "INR"
    serviceAreaId: Optional[str] = None
    reasonCode: Optional[str] = None


class AddressResponse(BaseModel):
    id: str
    label: str
    recipientName: str
    recipientMobile: str
    addressLine1: str
    addressLine2: Optional[str] = None
    landmark: Optional[str] = None
    locality: str
    subLocality: Optional[str] = None
    city: str
    district: str
    state: str
    postalCode: str
    country: str
    formattedAddress: str
    location: Optional[GeoJSONPointSchema] = None
    isDefault: bool
    deliveryInstructions: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
    serviceability: Optional[AddressServiceabilitySummary] = None


class AddressCreatedResponseData(BaseModel):
    id: str
    label: str
    recipientName: str
    recipientMobile: str
    formattedAddress: str
    isDefault: bool
    serviceability: AddressServiceabilitySummary


class AddressListResponseData(BaseModel):
    items: List[AddressResponse]
    total: int
    limit: int
    offset: int


class DefaultAddressResponseData(BaseModel):
    addressId: str
    isDefault: bool


class AddressDeleteResponseData(BaseModel):
    deletedAddressId: str
    newDefaultAddressId: Optional[str] = None
