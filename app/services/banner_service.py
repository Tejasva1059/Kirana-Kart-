from datetime import datetime, timezone
from typing import List, Optional
from app.db.mongodb import get_db
from app.schemas.banner import BannerItem


class BannerService:
    @staticmethod
    async def list_banners(
        service_area_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[BannerItem]:
        db = get_db()
        limit = min(max(limit, 1), 20)
        now = datetime.now(timezone.utc)

        query: dict = {
            "isActive": True,
            "$and": [
                {"$or": [{"startsAt": None}, {"startsAt": {"$exists": False}}, {"startsAt": {"$lte": now}}]},
                {"$or": [{"endsAt": None}, {"endsAt": {"$exists": False}}, {"endsAt": {"$gte": now}}]},
            ],
        }

        if service_area_id:
            query["$or"] = [
                {"serviceAreaIds": None},
                {"serviceAreaIds": {"$exists": False}},
                {"serviceAreaIds": {"$size": 0}},
                {"serviceAreaIds": service_area_id},
            ]

        cursor = db.banners.find(query).sort("position", 1).limit(limit)
        items: List[BannerItem] = []
        async for doc in cursor:
            items.append(
                BannerItem(
                    id=str(doc["_id"]),
                    title=doc.get("title", ""),
                    subtitle=doc.get("subtitle"),
                    imageUrl=doc.get("imageUrl", ""),
                    mobileImageUrl=doc.get("mobileImageUrl"),
                    targetType=doc.get("targetType", "none"),
                    targetId=doc.get("targetId"),
                    targetUrl=doc.get("targetUrl"),
                    position=doc.get("position", 1),
                )
            )
        return items
