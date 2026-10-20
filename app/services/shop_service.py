from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple, Union
from zoneinfo import ZoneInfo
from bson import ObjectId
from app.core.exceptions import BadRequestException, NotFoundException
from app.db.mongodb import get_db
from app.schemas.product import PaginationMeta
from app.schemas.shop import (
    ShopAvailabilityResponseData,
    ShopDetailResponseData,
    ShopListItem,
    ShopListResponseData,
)


class ShopService:
    DEFAULT_TIMEZONE = "Asia/Kolkata"

    @staticmethod
    def _to_object_id(val: Union[str, ObjectId]) -> Optional[ObjectId]:
        if isinstance(val, ObjectId):
            return val
        try:
            return ObjectId(val)
        except Exception:
            return None

    @classmethod
    def calculate_is_open(cls, shop_doc: dict) -> Tuple[bool, Optional[str]]:
        """
        Calculate if a shop is currently open based on its openingHours and timezone.
        Returns (is_open, next_opening_at).
        """
        if not shop_doc.get("isActive", True):
            return False, None

        tz_str = shop_doc.get("timezone") or cls.DEFAULT_TIMEZONE
        try:
            tz = ZoneInfo(tz_str)
        except Exception:
            tz = ZoneInfo(cls.DEFAULT_TIMEZONE)

        now = datetime.now(tz)
        weekday_name = now.strftime("%A").lower()  # monday, tuesday, etc.
        hours = shop_doc.get("openingHours") or {}

        day_hours = hours.get(weekday_name)
        if not day_hours:
            # If no opening hours defined, default to active status
            return True, None

        # Check explicit day toggle
        if day_hours.get("isOpen") is False:
            return False, None

        open_str = day_hours.get("openTime")
        close_str = day_hours.get("closeTime")
        if not open_str or not close_str:
            return True, None

        try:
            open_h, open_m = map(int, open_str.split(":"))
            close_h, close_m = map(int, close_str.split(":"))
            open_time = time(open_h, open_m)
            close_time = time(close_h, close_m)
        except Exception:
            return True, None

        current_time = now.time()

        is_open = False
        if open_time <= close_time:
            # Standard hours (e.g., 08:00 to 22:00)
            is_open = open_time <= current_time <= close_time
        else:
            # Overnight hours (e.g., 20:00 to 04:00)
            is_open = current_time >= open_time or current_time <= close_time

        if not is_open:
            return False, open_str

        # Check break periods
        breaks = day_hours.get("breaks") or []
        for brk in breaks:
            try:
                b_start = time(*map(int, brk["start"].split(":")))
                b_end = time(*map(int, brk["end"].split(":")))
                if b_start <= current_time <= b_end:
                    return False, brk.get("end")
            except Exception:
                continue

        return True, None

    @classmethod
    async def list_shops(
        cls,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        postal_code: Optional[str] = None,
        service_area_id: Optional[str] = None,
        category_id: Optional[str] = None,
        open_now: Optional[bool] = None,
        accepts_orders: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[ShopListItem], int]:
        db = get_db()
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)

        # Base query
        query: dict = {"isActive": True}

        if accepts_orders is not None:
            query["acceptsOrders"] = accepts_orders

        # Geo validation
        if (latitude is not None and longitude is None) or (latitude is None and longitude is not None):
            raise BadRequestException("Both latitude and longitude must be provided together.")
        if latitude is not None and longitude is not None:
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise BadRequestException("Latitude must be between -90 and 90 and longitude between -180 and 180.")

            # Find matching service areas for point
            from app.services.serviceability_service import ServiceabilityService
            matching_area_ids = []
            service_areas_cursor = db.service_areas.find({"enabled": True})
            async for sa in service_areas_cursor:
                polygon = sa.get("polygon")
                if polygon and polygon.get("coordinates"):
                    coords = polygon["coordinates"][0]
                    if ServiceabilityService.is_point_in_polygon(longitude, latitude, coords):
                        matching_area_ids.append(sa.get("serviceAreaId"))

            if matching_area_ids:
                query["serviceAreaIds"] = {"$in": matching_area_ids}
            else:
                # Outside all configured service areas
                return [], 0

        elif service_area_id:
            query["serviceAreaIds"] = service_area_id

        elif postal_code:
            # Postal code allowlist check
            # Match directly or through service areas
            matching_area_ids = []
            sa_cursor = db.service_areas.find({"enabled": True, "pincodes": postal_code})
            async for sa in sa_cursor:
                matching_area_ids.append(sa.get("serviceAreaId"))

            if matching_area_ids:
                query["$or"] = [
                    {"supportedPostalCodes": postal_code},
                    {"serviceAreaIds": {"$in": matching_area_ids}},
                ]
            else:
                query["supportedPostalCodes"] = postal_code

        cursor = db.shops.find(query).sort("name", 1)
        shops: List[ShopListItem] = []

        async for doc in cursor:
            s_id = str(doc["_id"])
            is_open, _ = cls.calculate_is_open(doc)

            if open_now is True and not is_open:
                continue

            shops.append(
                ShopListItem(
                    id=s_id,
                    name=doc.get("name", ""),
                    slug=doc.get("slug", ""),
                    logoUrl=doc.get("logoUrl"),
                    coverImageUrl=doc.get("coverImageUrl"),
                    isOpen=is_open,
                    acceptsOrders=doc.get("acceptsOrders", True),
                    serviceable=True,
                    serviceAreaIds=doc.get("serviceAreaIds", []),
                    supportedPostalCodes=doc.get("supportedPostalCodes", []),
                    location=doc.get("location"),
                    address=doc.get("address"),
                )
            )

        total = len(shops)
        paginated_shops = shops[offset : offset + limit]
        return paginated_shops, total

    @classmethod
    async def get_shop_by_id(cls, shop_id: str) -> ShopDetailResponseData:
        db = get_db()
        obj_id = cls._to_object_id(shop_id)
        query = {"$or": [{"_id": obj_id}, {"_id": shop_id}]} if obj_id else {"_id": shop_id}
        doc = await db.shops.find_one(query)

        if not doc or not doc.get("isActive", True):
            raise NotFoundException("Shop not found or inactive.", code="SHOP_NOT_FOUND")

        is_open, _ = cls.calculate_is_open(doc)
        return ShopDetailResponseData(
            id=str(doc["_id"]),
            name=doc.get("name", ""),
            slug=doc.get("slug", ""),
            description=doc.get("description"),
            logoUrl=doc.get("logoUrl"),
            coverImageUrl=doc.get("coverImageUrl"),
            contactPhone=doc.get("contactPhone"),
            address=doc.get("address"),
            location=doc.get("location"),
            serviceAreaIds=doc.get("serviceAreaIds", []),
            supportedPostalCodes=doc.get("supportedPostalCodes", []),
            openingHours=doc.get("openingHours", {}),
            timezone=doc.get("timezone", cls.DEFAULT_TIMEZONE),
            isActive=doc.get("isActive", True),
            isOpen=is_open,
            acceptsOrders=doc.get("acceptsOrders", True),
        )

    @classmethod
    async def get_shop_availability(
        cls,
        shop_id: str,
        service_area_id: Optional[str] = None,
    ) -> ShopAvailabilityResponseData:
        db = get_db()
        obj_id = cls._to_object_id(shop_id)
        query = {"$or": [{"_id": obj_id}, {"_id": shop_id}]} if obj_id else {"_id": shop_id}
        doc = await db.shops.find_one(query)

        if not doc:
            raise NotFoundException("Shop not found.", code="SHOP_NOT_FOUND")

        is_active = doc.get("isActive", True)
        accepts_orders = doc.get("acceptsOrders", True)
        is_open, next_opening = cls.calculate_is_open(doc)

        reason_code = "AVAILABLE"
        is_orderable = True

        if not is_active:
            reason_code = "SHOP_INACTIVE"
            is_orderable = False
        elif not is_open:
            reason_code = "SHOP_CLOSED"
            is_orderable = False
        elif not accepts_orders:
            reason_code = "SHOP_NOT_ACCEPTING_ORDERS"
            is_orderable = False
        elif service_area_id:
            shop_areas = doc.get("serviceAreaIds") or []
            if service_area_id not in shop_areas:
                reason_code = "SHOP_NOT_SERVICEABLE"
                is_orderable = False

        return ShopAvailabilityResponseData(
            shopId=str(doc["_id"]),
            isActive=is_active,
            isOpen=is_open,
            acceptsOrders=accepts_orders,
            isOrderable=is_orderable,
            timezone=doc.get("timezone", cls.DEFAULT_TIMEZONE),
            nextOpeningAt=next_opening,
            reasonCode=reason_code,
        )
