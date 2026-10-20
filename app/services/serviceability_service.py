from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from bson import ObjectId
from app.core.config import settings
from app.core.logging import logger
from app.db.mongodb import get_db
from app.schemas.serviceability import ServiceabilityResponseData


# Authoritative polygon boundary for the Indore rural & semi-urban launch cluster
# Bounding box covers Khudel, Index Medical College, Doublechowki, Baawliya, Morad, Sindhi Baroda
INDORE_LAUNCH_POLYGON = {
    "type": "Polygon",
    "coordinates": [
        [
            [75.9200, 22.6500],
            [76.0800, 22.6500],
            [76.0800, 22.7600],
            [75.9200, 22.7600],
            [75.9200, 22.6500],
        ]
    ],
}

DEFAULT_LAUNCH_SERVICE_AREA = {
    "serviceAreaId": "indore-launch-area",
    "name": "Indore Launch Cluster (Khudel - Index Medical College)",
    "enabled": True,
    "deliveryCharge": 0,
    "currency": "INR",
    "pincodes": ["453115", "452016", "455223"],
    "localities": [
        "Index Medical College",
        "Khudel",
        "Doublechowki",
        "Baawliya",
        "Morad",
        "Sindhi Baroda",
        "Khudel Khurd",
    ],
    "polygon": INDORE_LAUNCH_POLYGON,
}


def is_point_in_polygon(lon: float, lat: float, polygon_coords: List[List[float]]) -> bool:
    """Ray casting point-in-polygon algorithm."""
    x, y = lon, lat
    n = len(polygon_coords)
    inside = False
    p1x, p1y = polygon_coords[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon_coords[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


class ServiceabilityService:
    @staticmethod
    async def seed_default_service_areas_if_needed() -> None:
        """Seed initial launch service area if not already present."""
        db = get_db()
        existing = await db.service_areas.find_one({"serviceAreaId": DEFAULT_LAUNCH_SERVICE_AREA["serviceAreaId"]})
        if not existing:
            now = datetime.now(timezone.utc)
            doc = {**DEFAULT_LAUNCH_SERVICE_AREA, "createdAt": now, "updatedAt": now}
            await db.service_areas.insert_one(doc)
            logger.info("Seeded initial Indore launch service area.")

    @staticmethod
    async def check_serviceability(
        postal_code: Optional[str] = None,
        city: Optional[str] = None,
        locality: Optional[str] = None,
        coordinates: Optional[List[float]] = None,  # [lon, lat]
    ) -> ServiceabilityResponseData:
        """
        Evaluate delivery eligibility against configured service areas.
        Coordinates take precedence, followed by PIN code and locality rules.
        Fail-closed: returns isServiceable=False if no rule confirms delivery eligibility.
        """
        db = get_db()
        now = datetime.now(timezone.utc)

        # Ensure launch area exists
        await ServiceabilityService.seed_default_service_areas_if_needed()

        service_areas_cursor = db.service_areas.find({"enabled": True})
        active_areas = await service_areas_cursor.to_list(length=100)

        if not active_areas:
            return ServiceabilityResponseData(
                isServiceable=False,
                serviceAreaId=None,
                deliveryCharge=None,
                currency=settings.DEFAULT_CURRENCY,
                reasonCode="SERVICE_AREA_NOT_CONFIGURED",
                estimatedDeliveryMinutes=None,
            )

        # 1. Geographic coordinate point-in-polygon verification
        if coordinates and len(coordinates) == 2:
            lon, lat = coordinates[0], coordinates[1]
            for area in active_areas:
                poly = area.get("polygon")
                if poly and poly.get("type") == "Polygon" and poly.get("coordinates"):
                    ring = poly["coordinates"][0]
                    if is_point_in_polygon(lon, lat, ring):
                        return ServiceabilityResponseData(
                            isServiceable=True,
                            serviceAreaId=area.get("serviceAreaId", "indore-launch-area"),
                            deliveryCharge=area.get("deliveryCharge", 0),
                            currency=area.get("currency", "INR"),
                            reasonCode="WITHIN_SERVICE_AREA",
                            estimatedDeliveryMinutes=None,
                        )

        # 2. PIN code verification
        if postal_code:
            clean_pin = postal_code.strip()
            for area in active_areas:
                if clean_pin in area.get("pincodes", []):
                    return ServiceabilityResponseData(
                        isServiceable=True,
                        serviceAreaId=area.get("serviceAreaId", "indore-launch-area"),
                        deliveryCharge=area.get("deliveryCharge", 0),
                        currency=area.get("currency", "INR"),
                        reasonCode="WITHIN_SERVICE_AREA",
                        estimatedDeliveryMinutes=None,
                    )

        # 3. Locality name verification
        if locality:
            clean_locality = locality.strip().lower()
            for area in active_areas:
                area_localities = [loc.strip().lower() for loc in area.get("localities", [])]
                for configured_loc in area_localities:
                    if configured_loc in clean_locality or clean_locality in configured_loc:
                        return ServiceabilityResponseData(
                            isServiceable=True,
                            serviceAreaId=area.get("serviceAreaId", "indore-launch-area"),
                            deliveryCharge=area.get("deliveryCharge", 0),
                            currency=area.get("currency", "INR"),
                            reasonCode="WITHIN_SERVICE_AREA",
                            estimatedDeliveryMinutes=None,
                        )

        # Fail closed: Outside configured service area
        return ServiceabilityResponseData(
            isServiceable=False,
            serviceAreaId=None,
            deliveryCharge=None,
            currency=settings.DEFAULT_CURRENCY,
            reasonCode="OUTSIDE_SERVICE_AREA",
            estimatedDeliveryMinutes=None,
        )
