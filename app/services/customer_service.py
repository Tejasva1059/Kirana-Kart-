from datetime import datetime, timezone
from typing import Any, Dict, Optional
from bson import ObjectId
from pymongo import ReturnDocument
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.core.security import normalize_email
from app.db.mongodb import get_db
from app.schemas.customer import CustomerPublicProfile


class CustomerService:
    @staticmethod
    def map_to_public_profile(doc: Dict[str, Any]) -> CustomerPublicProfile:
        doc_id = str(doc.get("_id"))
        return CustomerPublicProfile(
            id=doc_id,
            fullName=doc["fullName"],
            email=doc.get("emailNormalized"),
            mobileNumber=doc["mobileNumberNormalized"],
            role=doc.get("role", "customer"),
            status=doc.get("status", "active"),
            createdAt=doc.get("createdAt"),
        )

    @staticmethod
    async def get_customer_by_id(customer_id: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        query: Dict[str, Any] = {}
        if ObjectId.is_valid(customer_id):
            query = {"_id": ObjectId(customer_id)}
        else:
            query = {"_id": customer_id}
        return await db.customers.find_one(query)

    @staticmethod
    async def get_customer_by_mobile(mobile_number: str) -> Optional[Dict[str, Any]]:
        db = get_db()
        return await db.customers.find_one({"mobileNumberNormalized": mobile_number})

    @staticmethod
    async def update_profile(
        customer_id: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> CustomerPublicProfile:
        db = get_db()
        now = datetime.now(timezone.utc)
        update_fields: Dict[str, Any] = {"updatedAt": now}

        if full_name is not None:
            cleaned_name = full_name.strip()
            if len(cleaned_name) < 2 or len(cleaned_name) > 100:
                raise BadRequestException("Full name must be between 2 and 100 characters.", code="INVALID_NAME")
            update_fields["fullName"] = cleaned_name

        if email is not None:
            normalized_email = normalize_email(email)
            # Check unique email across other customers
            existing_email = await db.customers.find_one({
                "emailNormalized": normalized_email,
                "_id": {"$ne": ObjectId(customer_id) if ObjectId.is_valid(customer_id) else customer_id},
            })
            if existing_email:
                raise ConflictException("An account with this email address already exists.", code="EMAIL_ALREADY_EXISTS")
            update_fields["emailNormalized"] = normalized_email

        query: Dict[str, Any] = {"_id": ObjectId(customer_id) if ObjectId.is_valid(customer_id) else customer_id}
        updated_doc = await db.customers.find_one_and_update(
            query,
            {"$set": update_fields},
            return_document=ReturnDocument.AFTER,
        )

        if not updated_doc:
            raise NotFoundException("Customer profile not found.", code="CUSTOMER_NOT_FOUND")

        return CustomerService.map_to_public_profile(updated_doc)
