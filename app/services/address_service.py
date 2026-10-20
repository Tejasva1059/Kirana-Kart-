from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo import ReturnDocument
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
)
from app.core.logging import logger
from app.db.mongodb import get_db
from app.schemas.address import (
    AddressCreatedResponseData,
    AddressCreateRequest,
    AddressDeleteResponseData,
    AddressListResponseData,
    AddressResponse,
    AddressServiceabilitySummary,
    AddressUpdateRequest,
    DefaultAddressResponseData,
    GeoJSONPointSchema,
)
from app.services.geocoding_service import get_geocoding_provider
from app.services.serviceability_service import ServiceabilityService


def build_customer_id_query(customer_id: str) -> Dict[str, Any]:
    """Build query matching either ObjectId or string representation of customerId."""
    if ObjectId.is_valid(customer_id):
        return {"$in": [ObjectId(customer_id), str(customer_id)]}
    return str(customer_id)


def build_formatted_address(
    address_line_1: str,
    locality: str,
    city: str,
    state: str,
    postal_code: str,
    country: str,
    address_line_2: Optional[str] = None,
    landmark: Optional[str] = None,
    sub_locality: Optional[str] = None,
) -> str:
    """Build normalized, human-readable address line."""
    parts = [address_line_1]
    if address_line_2:
        parts.append(address_line_2)
    if landmark:
        parts.append(f"Near {landmark}" if not landmark.lower().startswith("near") else landmark)
    if sub_locality:
        parts.append(sub_locality)
    parts.extend([locality, city, state, f"{postal_code}, {country}"])
    return ", ".join(p.strip() for p in parts if p and p.strip())


class AddressService:
    @staticmethod
    def map_to_response(doc: Dict[str, Any], serviceability: Optional[AddressServiceabilitySummary] = None) -> AddressResponse:
        location_obj = None
        raw_loc = doc.get("location")
        if raw_loc and isinstance(raw_loc, dict) and raw_loc.get("type") == "Point" and raw_loc.get("coordinates"):
            location_obj = GeoJSONPointSchema(
                type="Point",
                coordinates=raw_loc["coordinates"],
            )

        return AddressResponse(
            id=str(doc["_id"]),
            label=doc.get("label", "Home"),
            recipientName=doc.get("recipientName", ""),
            recipientMobile=doc.get("recipientMobile", ""),
            addressLine1=doc.get("addressLine1", ""),
            addressLine2=doc.get("addressLine2"),
            landmark=doc.get("landmark"),
            locality=doc.get("locality", ""),
            subLocality=doc.get("subLocality"),
            city=doc.get("city", ""),
            district=doc.get("district", ""),
            state=doc.get("state", ""),
            postalCode=doc.get("postalCode", ""),
            country=doc.get("country", "India"),
            formattedAddress=doc.get("formattedAddress", ""),
            location=location_obj,
            isDefault=bool(doc.get("isDefault", False)),
            deliveryInstructions=doc.get("deliveryInstructions"),
            createdAt=doc.get("createdAt", datetime.now(timezone.utc)),
            updatedAt=doc.get("updatedAt", datetime.now(timezone.utc)),
            serviceability=serviceability,
        )

    @staticmethod
    async def list_addresses(
        customer_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> AddressListResponseData:
        """
        Retrieve saved addresses belonging to the authenticated customer.
        Returns default address first, followed by most recently updated.
        """
        db = get_db()
        query = {"customerId": build_customer_id_query(customer_id)}

        total = await db.addresses.count_documents(query)
        cursor = (
            db.addresses.find(query)
            .sort([("isDefault", -1), ("updatedAt", -1)])
            .skip(offset)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)

        items: List[AddressResponse] = []
        for doc in docs:
            # Check serviceability for each address
            coords = doc.get("location", {}).get("coordinates") if doc.get("location") else None
            serv_res = await ServiceabilityService.check_serviceability(
                postal_code=doc.get("postalCode"),
                city=doc.get("city"),
                locality=doc.get("locality"),
                coordinates=coords,
            )
            serv_summary = AddressServiceabilitySummary(
                isServiceable=serv_res.isServiceable,
                deliveryCharge=serv_res.deliveryCharge,
                currency=serv_res.currency,
                serviceAreaId=serv_res.serviceAreaId,
                reasonCode=serv_res.reasonCode,
            )
            items.append(AddressService.map_to_response(doc, serviceability=serv_summary))

        return AddressListResponseData(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    async def create_address(
        customer_id: str,
        payload: AddressCreateRequest,
    ) -> AddressCreatedResponseData:
        """
        Create a new customer address, geocode if missing, enforce default rules,
        and assess delivery serviceability.
        """
        db = get_db()
        now = datetime.now(timezone.utc)
        cust_query = {"customerId": build_customer_id_query(customer_id)}

        # 1. Geocode location if not explicitly provided
        location_dict: Optional[Dict[str, Any]] = None
        if payload.location:
            location_dict = payload.location.model_dump()
        else:
            geocoder = get_geocoding_provider()
            search_str = f"{payload.addressLine1}, {payload.locality}, {payload.city}, {payload.postalCode}"
            geocoded = await geocoder.geocode_address(search_str)
            if geocoded:
                location_dict = geocoded

        # 2. Build formatted address
        formatted_addr = build_formatted_address(
            address_line_1=payload.addressLine1,
            locality=payload.locality,
            city=payload.city,
            state=payload.state,
            postal_code=payload.postalCode,
            country=payload.country,
            address_line_2=payload.addressLine2,
            landmark=payload.landmark,
            sub_locality=payload.subLocality,
        )

        # 3. Handle default address logic
        existing_count = await db.addresses.count_documents(cust_query)
        is_default = payload.isDefault

        # First address is automatically default
        if existing_count == 0:
            is_default = True

        if is_default and existing_count > 0:
            # Unset existing defaults for this customer atomically
            await db.addresses.update_many(cust_query, {"$set": {"isDefault": False}})

        # 4. Insert address document
        doc = {
            "customerId": str(customer_id),
            "label": payload.label,
            "recipientName": payload.recipientName,
            "recipientMobile": payload.recipientMobile,
            "addressLine1": payload.addressLine1,
            "addressLine2": payload.addressLine2,
            "landmark": payload.landmark,
            "locality": payload.locality,
            "subLocality": payload.subLocality,
            "city": payload.city,
            "district": payload.district,
            "state": payload.state,
            "postalCode": payload.postalCode,
            "country": payload.country,
            "formattedAddress": formatted_addr,
            "location": location_dict,
            "isDefault": is_default,
            "deliveryInstructions": payload.deliveryInstructions,
            "createdAt": now,
            "updatedAt": now,
        }

        result = await db.addresses.insert_one(doc)
        doc_id = str(result.inserted_id)

        # 5. Determine delivery serviceability
        coords = location_dict.get("coordinates") if location_dict else None
        serv_res = await ServiceabilityService.check_serviceability(
            postal_code=payload.postalCode,
            city=payload.city,
            locality=payload.locality,
            coordinates=coords,
        )

        return AddressCreatedResponseData(
            id=doc_id,
            label=payload.label,
            recipientName=payload.recipientName,
            recipientMobile=payload.recipientMobile,
            formattedAddress=formatted_addr,
            isDefault=is_default,
            serviceability=AddressServiceabilitySummary(
                isServiceable=serv_res.isServiceable,
                deliveryCharge=serv_res.deliveryCharge,
                currency=serv_res.currency,
                serviceAreaId=serv_res.serviceAreaId,
                reasonCode=serv_res.reasonCode,
            ),
        )

    @staticmethod
    async def get_address(customer_id: str, address_id: str) -> AddressResponse:
        """Fetch single address with ownership validation."""
        if not ObjectId.is_valid(address_id):
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        db = get_db()
        query = {
            "_id": ObjectId(address_id),
            "customerId": build_customer_id_query(customer_id),
        }
        doc = await db.addresses.find_one(query)
        if not doc:
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        coords = doc.get("location", {}).get("coordinates") if doc.get("location") else None
        serv_res = await ServiceabilityService.check_serviceability(
            postal_code=doc.get("postalCode"),
            city=doc.get("city"),
            locality=doc.get("locality"),
            coordinates=coords,
        )

        serv_summary = AddressServiceabilitySummary(
            isServiceable=serv_res.isServiceable,
            deliveryCharge=serv_res.deliveryCharge,
            currency=serv_res.currency,
            serviceAreaId=serv_res.serviceAreaId,
            reasonCode=serv_res.reasonCode,
        )
        return AddressService.map_to_response(doc, serviceability=serv_summary)

    @staticmethod
    async def update_address(
        customer_id: str,
        address_id: str,
        payload: AddressUpdateRequest,
    ) -> AddressResponse:
        """Update address with allowlist validation and ownership enforcement."""
        if not ObjectId.is_valid(address_id):
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        db = get_db()
        cust_q = build_customer_id_query(customer_id)
        query = {
            "_id": ObjectId(address_id),
            "customerId": cust_q,
        }
        existing = await db.addresses.find_one(query)
        if not existing:
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        now = datetime.now(timezone.utc)
        update_data: Dict[str, Any] = {"updatedAt": now}

        # Apply allowlisted fields
        raw_updates = payload.model_dump(exclude_unset=True)
        for key in [
            "label", "recipientName", "recipientMobile", "addressLine1", "addressLine2",
            "landmark", "locality", "subLocality", "city", "district", "state",
            "postalCode", "country", "deliveryInstructions"
        ]:
            if key in raw_updates:
                update_data[key] = raw_updates[key]

        # Handle Location & re-geocoding
        address_text_changed = any(
            k in raw_updates for k in ["addressLine1", "locality", "city", "postalCode"]
        )

        if "location" in raw_updates:
            loc = raw_updates["location"]
            update_data["location"] = loc if loc else None
        elif address_text_changed:
            # Recompute geocode when text changes without explicit coordinates
            line1 = update_data.get("addressLine1", existing.get("addressLine1", ""))
            locality = update_data.get("locality", existing.get("locality", ""))
            city = update_data.get("city", existing.get("city", ""))
            pin = update_data.get("postalCode", existing.get("postalCode", ""))
            geocoder = get_geocoding_provider()
            geocoded = await geocoder.geocode_address(f"{line1}, {locality}, {city}, {pin}")
            update_data["location"] = geocoded

        # Rebuild formattedAddress if components modified
        if address_text_changed or "addressLine2" in raw_updates or "landmark" in raw_updates:
            update_data["formattedAddress"] = build_formatted_address(
                address_line_1=update_data.get("addressLine1", existing.get("addressLine1", "")),
                locality=update_data.get("locality", existing.get("locality", "")),
                city=update_data.get("city", existing.get("city", "")),
                state=update_data.get("state", existing.get("state", "")),
                postal_code=update_data.get("postalCode", existing.get("postalCode", "")),
                country=update_data.get("country", existing.get("country", "India")),
                address_line_2=update_data.get("addressLine2", existing.get("addressLine2")),
                landmark=update_data.get("landmark", existing.get("landmark")),
                sub_locality=update_data.get("subLocality", existing.get("subLocality")),
            )

        # Handle default address update
        if "isDefault" in raw_updates:
            new_default = bool(raw_updates["isDefault"])
            if new_default:
                await db.addresses.update_many(
                    {"customerId": cust_q, "_id": {"$ne": ObjectId(address_id)}},
                    {"$set": {"isDefault": False}},
                )
            update_data["isDefault"] = new_default

        updated_doc = await db.addresses.find_one_and_update(
            query,
            {"$set": update_data},
            return_document=ReturnDocument.AFTER,
        )

        coords = updated_doc.get("location", {}).get("coordinates") if updated_doc.get("location") else None
        serv_res = await ServiceabilityService.check_serviceability(
            postal_code=updated_doc.get("postalCode"),
            city=updated_doc.get("city"),
            locality=updated_doc.get("locality"),
            coordinates=coords,
        )
        serv_summary = AddressServiceabilitySummary(
            isServiceable=serv_res.isServiceable,
            deliveryCharge=serv_res.deliveryCharge,
            currency=serv_res.currency,
            serviceAreaId=serv_res.serviceAreaId,
            reasonCode=serv_res.reasonCode,
        )
        return AddressService.map_to_response(updated_doc, serviceability=serv_summary)

    @staticmethod
    async def delete_address(customer_id: str, address_id: str) -> AddressDeleteResponseData:
        """
        Delete address. If deleted address was default, deterministically reassign
        the most recently updated remaining address as default.
        """
        if not ObjectId.is_valid(address_id):
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        db = get_db()
        cust_q = build_customer_id_query(customer_id)
        query = {
            "_id": ObjectId(address_id),
            "customerId": cust_q,
        }

        existing = await db.addresses.find_one(query)
        if not existing:
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        was_default = existing.get("isDefault", False)
        await db.addresses.delete_one(query)

        new_default_id: Optional[str] = None
        if was_default:
            # Deterministically assign most recently updated remaining address
            remaining = (
                await db.addresses.find({"customerId": cust_q})
                .sort([("updatedAt", -1)])
                .to_list(length=1)
            )
            if remaining:
                new_default_id = str(remaining[0]["_id"])
                await db.addresses.update_one(
                    {"_id": remaining[0]["_id"]},
                    {"$set": {"isDefault": True, "updatedAt": datetime.now(timezone.utc)}},
                )

        return AddressDeleteResponseData(
            deletedAddressId=address_id,
            newDefaultAddressId=new_default_id,
        )

    @staticmethod
    async def set_default_address(customer_id: str, address_id: str) -> DefaultAddressResponseData:
        """
        Atomically set specified address as customer's default and unset previous default.
        """
        if not ObjectId.is_valid(address_id):
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        db = get_db()
        cust_q = build_customer_id_query(customer_id)
        target_obj_id = ObjectId(address_id)

        target = await db.addresses.find_one({"_id": target_obj_id, "customerId": cust_q})
        if not target:
            raise NotFoundException("Address not found.", code="ADDRESS_NOT_FOUND")

        # Concurrency-safe: unset other defaults then set new default
        await db.addresses.update_many(
            {"customerId": cust_q, "_id": {"$ne": target_obj_id}},
            {"$set": {"isDefault": False}},
        )

        await db.addresses.update_one(
            {"_id": target_obj_id, "customerId": cust_q},
            {"$set": {"isDefault": True, "updatedAt": datetime.now(timezone.utc)}},
        )

        return DefaultAddressResponseData(
            addressId=address_id,
            isDefault=True,
        )
