from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import NotFoundException
from app.db.mongodb import get_db
from app.schemas.wishlist import WishlistItemResponse, WishlistResponseData


class WishlistService:
    @staticmethod
    def _to_object_id(val: Union[str, ObjectId, None]) -> Optional[ObjectId]:
        if not val:
            return None
        if isinstance(val, ObjectId):
            return val
        try:
            return ObjectId(val)
        except Exception:
            return None

    @classmethod
    async def get_or_create_wishlist_doc(cls, customer_id: str) -> dict:
        """Fetch or create customer's wishlist document."""
        db = get_db()
        doc = await db.wishlists.find_one({"customerId": customer_id})
        if doc:
            return doc

        now = datetime.now(timezone.utc)
        new_doc = {
            "_id": ObjectId(),
            "customerId": customer_id,
            "items": [],
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            await db.wishlists.insert_one(new_doc)
            return new_doc
        except DuplicateKeyError:
            doc = await db.wishlists.find_one({"customerId": customer_id})
            if doc:
                return doc
            raise

    @classmethod
    async def get_wishlist(
        cls,
        customer_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> WishlistResponseData:
        """Fetch the authenticated customer's wishlist with enriched product details."""
        db = get_db()
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)

        doc = await db.wishlists.find_one({"customerId": customer_id})
        if not doc or not doc.get("items"):
            return WishlistResponseData(
                wishlistId=f"empty_{customer_id}",
                customerId=customer_id,
                items=[],
                totalCount=0,
            )

        items_raw = doc.get("items", [])
        total_count = len(items_raw)
        paginated_raw = items_raw[offset : offset + limit]

        prod_ids = [cls._to_object_id(it.get("productId")) or it.get("productId") for it in paginated_raw]
        products_map: Dict[str, dict] = {}
        async for p in db.products.find({"_id": {"$in": prod_ids}}):
            products_map[str(p["_id"])] = p

        # Fetch variants to determine lowest price and stock availability
        variants_map: Dict[str, List[dict]] = {}
        async for v in db.product_variants.find({"productId": {"$in": prod_ids + [str(pid) for pid in prod_ids]}}):
            v_pid = str(v.get("productId"))
            variants_map.setdefault(v_pid, []).append(v)

        enriched_items: List[WishlistItemResponse] = []
        for it in paginated_raw:
            pid = str(it.get("productId"))
            added_at = it.get("addedAt", doc.get("createdAt", datetime.now(timezone.utc)))
            product = products_map.get(pid)

            if not product:
                # Deleted product - show placeholder
                enriched_items.append(
                    WishlistItemResponse(
                        productId=pid,
                        productName="Discontinued Product",
                        slug="discontinued",
                        categoryId="unknown",
                        isAvailable=False,
                        availableQuantity=0,
                        addedAt=added_at,
                    )
                )
                continue

            variants = variants_map.get(pid, [])
            min_price_paise = None
            max_mrp_paise = None
            total_stock = 0
            is_avail = False

            if product.get("isActive", True):
                for v in variants:
                    if v.get("isActive", True):
                        vp = v.get("pricePaise")
                        if vp is not None and (min_price_paise is None or vp < min_price_paise):
                            min_price_paise = vp
                            max_mrp_paise = v.get("mrpPaise")
                        total_stock += 10
                        is_avail = True

            enriched_items.append(
                WishlistItemResponse(
                    productId=pid,
                    productName=product.get("name", ""),
                    slug=product.get("slug", ""),
                    brand=product.get("brand"),
                    categoryId=str(product.get("categoryId", "")),
                    imageUrl=product.get("imageUrl"),
                    pricePaise=min_price_paise,
                    price=round(min_price_paise / 100.0, 2) if min_price_paise is not None else None,
                    mrpPaise=max_mrp_paise,
                    isAvailable=is_avail,
                    availableQuantity=total_stock,
                    addedAt=added_at,
                )
            )

        return WishlistResponseData(
            wishlistId=str(doc["_id"]),
            customerId=customer_id,
            items=enriched_items,
            totalCount=total_count,
        )

    @classmethod
    async def add_item(cls, customer_id: str, product_id: str) -> WishlistItemResponse:
        """Add a product to customer's wishlist idempotently."""
        db = get_db()
        p_obj_id = cls._to_object_id(product_id)
        p_query = {"$or": [{"_id": p_obj_id}, {"_id": product_id}]} if p_obj_id else {"_id": product_id}
        product = await db.products.find_one(p_query)
        if not product or not product.get("isActive", True):
            raise NotFoundException("Product not found or inactive.", code="PRODUCT_NOT_FOUND")

        actual_pid = str(product["_id"])
        doc = await cls.get_or_create_wishlist_doc(customer_id)
        now = datetime.now(timezone.utc)

        items: List[dict] = doc.get("items", [])
        existing_item = None
        for it in items:
            if str(it.get("productId")) == actual_pid:
                existing_item = it
                break

        if not existing_item:
            new_item = {"productId": actual_pid, "addedAt": now}
            items.append(new_item)
            await db.wishlists.update_one(
                {"_id": doc["_id"]},
                {"$set": {"items": items, "updatedAt": now}},
            )
            added_at = now
        else:
            added_at = existing_item.get("addedAt", now)

        # Fetch variants to get price info
        min_price_paise = None
        max_mrp_paise = None
        total_stock = 0
        is_avail = False
        v_cursor = db.product_variants.find({"productId": {"$in": [actual_pid, p_obj_id] if p_obj_id else [actual_pid]}})
        async for v in v_cursor:
            if v.get("isActive", True):
                vp = v.get("pricePaise")
                if vp is not None and (min_price_paise is None or vp < min_price_paise):
                    min_price_paise = vp
                    max_mrp_paise = v.get("mrpPaise")
                total_stock += 10
                is_avail = True

        return WishlistItemResponse(
            productId=actual_pid,
            productName=product.get("name", ""),
            slug=product.get("slug", ""),
            brand=product.get("brand"),
            categoryId=str(product.get("categoryId", "")),
            imageUrl=product.get("imageUrl"),
            pricePaise=min_price_paise,
            price=round(min_price_paise / 100.0, 2) if min_price_paise is not None else None,
            mrpPaise=max_mrp_paise,
            isAvailable=is_avail,
            availableQuantity=total_stock,
            addedAt=added_at,
        )

    @classmethod
    async def remove_item(cls, customer_id: str, product_id: str) -> bool:
        """Remove a product from customer's wishlist idempotently."""
        db = get_db()
        doc = await db.wishlists.find_one({"customerId": customer_id})
        if not doc or not doc.get("items"):
            return True

        p_obj_id = cls._to_object_id(product_id)
        target_ids = {str(product_id)}
        if p_obj_id:
            target_ids.add(str(p_obj_id))

        items: List[dict] = doc.get("items", [])
        new_items = [it for it in items if str(it.get("productId")) not in target_ids]

        now = datetime.now(timezone.utc)
        await db.wishlists.update_one(
            {"_id": doc["_id"]},
            {"$set": {"items": new_items, "updatedAt": now}},
        )
        return True
