from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId
from app.core.exceptions import BadRequestException
from app.core.logging import logger
from app.db.mongodb import get_db
from app.schemas.product import (
    PaginationMeta,
    ProductAvailabilitySummary,
    ProductPrice,
)
from app.schemas.search import (
    SearchCategoryItem,
    SearchProductItem,
    SearchSuggestionItem,
    TrendingSearchItem,
)
from app.schemas.variant import ProductVariantItem


class SearchService:
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
    def validate_category_id(cls, category_id: Optional[str]) -> None:
        if not category_id:
            return
        clean_id = category_id.strip()
        if not clean_id:
            raise BadRequestException("Invalid categoryId format.", code="INVALID_CATEGORY_ID")
        if not ObjectId.is_valid(clean_id) and not re.match(r"^[a-zA-Z0-9_-]{3,50}$", clean_id):
            raise BadRequestException("Invalid categoryId format.", code="INVALID_CATEGORY_ID")

    @classmethod
    def validate_shop_id(cls, shop_id: Optional[str]) -> None:
        if not shop_id:
            return
        clean_id = shop_id.strip()
        if not clean_id:
            raise BadRequestException("Invalid shopId format.", code="INVALID_SHOP_ID")
        if not ObjectId.is_valid(clean_id) and not re.match(r"^[a-zA-Z0-9_-]{3,50}$", clean_id):
            raise BadRequestException("Invalid shopId format.", code="INVALID_SHOP_ID")

    @classmethod
    def validate_sort(cls, sort: str) -> str:
        valid_sorts = {"relevance", "price_asc", "price_desc", "name_asc", "newest"}
        clean = sort.strip().lower() if sort else "relevance"
        if clean not in valid_sorts:
            raise BadRequestException(
                f"Unsupported sort value '{sort}'. Supported values: relevance, price_asc, price_desc, name_asc, newest.",
                code="UNSUPPORTED_SORT",
            )
        return clean

    @classmethod
    async def get_eligible_shop_ids(
        cls,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
    ) -> List[str]:
        db = get_db()
        if shop_id:
            cls.validate_shop_id(shop_id)
            obj_id = cls._to_object_id(shop_id)
            query = {"$or": [{"_id": obj_id}, {"_id": shop_id}]} if obj_id else {"_id": shop_id}
            shop = await db.shops.find_one(query)
            if not shop or not shop.get("isActive", True):
                return []
            if service_area_id and service_area_id not in (shop.get("serviceAreaIds") or []):
                return []
            return [str(shop["_id"])]

        if service_area_id:
            cursor = db.shops.find({"isActive": True, "serviceAreaIds": service_area_id})
            shop_ids = []
            async for s in cursor:
                shop_ids.append(str(s["_id"]))
            return shop_ids

        # If no shop or service area specified, resolve all active shops that accept orders
        cursor = db.shops.find({"isActive": True})
        shop_ids = []
        async for s in cursor:
            shop_ids.append(str(s["_id"]))
        return shop_ids

    @classmethod
    async def search_products(
        cls,
        q: str,
        category_id: Optional[str] = None,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
        brand: Optional[str] = None,
        in_stock: Optional[bool] = None,
        sort_by: str = "relevance",
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[SearchProductItem], PaginationMeta]:
        db = get_db()

        # Validation
        if not q or not q.strip():
            raise BadRequestException("Search query 'q' cannot be empty.", code="EMPTY_SEARCH_QUERY")

        clean_q = q.strip()
        if len(clean_q) < 1:
            raise BadRequestException("Search query 'q' cannot be empty.", code="EMPTY_SEARCH_QUERY")

        cls.validate_category_id(category_id)
        sort_by = cls.validate_sort(sort_by)

        if min_price is not None and min_price < 0:
            raise BadRequestException("minPrice cannot be negative.", code="INVALID_PRICE")
        if max_price is not None and max_price < 0:
            raise BadRequestException("maxPrice cannot be negative.", code="INVALID_PRICE")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise BadRequestException("minPrice cannot be greater than maxPrice.", code="INVALID_PRICE_RANGE")

        if page < 1:
            raise BadRequestException("page must be greater than or equal to 1.", code="INVALID_PAGE")
        if limit < 1 or limit > 50:
            raise BadRequestException("limit must be between 1 and 50.", code="INVALID_LIMIT")

        # 1. Look up any categories whose name matches clean_q to include in search
        cat_matches_cursor = db.categories.find({
            "isActive": True,
            "name": {"$regex": re.escape(clean_q), "$options": "i"},
        })
        matching_cat_ids = []
        async for c_doc in cat_matches_cursor:
            matching_cat_ids.append(c_doc["_id"])
            matching_cat_ids.append(str(c_doc["_id"]))

        # 2. Look up any product variants whose SKU matches clean_q
        v_matches_cursor = db.product_variants.find({
            "isActive": True,
            "sku": {"$regex": re.escape(clean_q), "$options": "i"},
        })
        matching_sku_prod_ids = []
        async for v_doc in v_matches_cursor:
            matching_sku_prod_ids.append(v_doc.get("productId"))

        # 3. Base product query
        safe_q = re.escape(clean_q)
        or_clauses: List[Dict[str, Any]] = [
            {"name": {"$regex": safe_q, "$options": "i"}},
            {"brand": {"$regex": safe_q, "$options": "i"}},
            {"searchKeywords": {"$regex": safe_q, "$options": "i"}},
        ]
        if matching_cat_ids:
            or_clauses.append({"categoryId": {"$in": matching_cat_ids}})
        if matching_sku_prod_ids:
            or_clauses.append({"_id": {"$in": matching_sku_prod_ids}})

        query: Dict[str, Any] = {"isActive": True, "$or": or_clauses}

        if category_id:
            cat_obj_id = cls._to_object_id(category_id)
            query["categoryId"] = {"$in": [cat_obj_id, category_id]} if cat_obj_id else category_id

        if brand:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}

        # 4. Fetch matching products from MongoDB
        matched_products: List[Dict[str, Any]] = []
        cursor = db.products.find(query)
        async for p in cursor:
            matched_products.append(p)

        if not matched_products:
            # Record search event with 0 results
            await cls.record_search_event(clean_q, result_count=0)
            return [], PaginationMeta(total=0, page=page, limit=limit, totalPages=0, offset=0, hasMore=False)

        # 5. Fetch all categories to populate category metadata
        all_cat_ids = list(set([p.get("categoryId") for p in matched_products if p.get("categoryId")]))
        obj_cat_ids = [cls._to_object_id(cid) for cid in all_cat_ids if cls._to_object_id(cid)]
        combined_cat_ids = list(set(all_cat_ids + obj_cat_ids))
        categories_map: Dict[str, SearchCategoryItem] = {}
        if combined_cat_ids:
            cat_cursor = db.categories.find({"_id": {"$in": combined_cat_ids}})
            async for c in cat_cursor:
                c_id_str = str(c["_id"])
                c_item = SearchCategoryItem(id=c_id_str, name=c.get("name", ""), slug=c.get("slug"))
                categories_map[c_id_str] = c_item

        # 6. Fetch variants and shop inventory
        product_ids = [p["_id"] for p in matched_products]
        p_id_strs = [str(pid) for pid in product_ids]
        combined_p_ids = list(set(product_ids + p_id_strs))

        variants_cursor = db.product_variants.find(
            {"productId": {"$in": combined_p_ids}, "isActive": True}
        ).sort([("packSize", 1)])
        variants_by_product: Dict[str, List[Dict[str, Any]]] = {}
        all_variant_ids = []
        async for v in variants_cursor:
            pid = str(v.get("productId"))
            all_variant_ids.append(v["_id"])
            all_variant_ids.append(str(v["_id"]))
            variants_by_product.setdefault(pid, []).append(v)

        eligible_shop_ids = await cls.get_eligible_shop_ids(shop_id, service_area_id)
        inventory_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        if eligible_shop_ids and all_variant_ids:
            inv_query: Dict[str, Any] = {
                "shopId": {"$in": eligible_shop_ids + [cls._to_object_id(sid) for sid in eligible_shop_ids if cls._to_object_id(sid)]},
                "variantId": {"$in": all_variant_ids},
            }
            inv_cursor = db.shop_inventory.find(inv_query)
            async for inv in inv_cursor:
                s_id = str(inv["shopId"])
                v_id = str(inv["variantId"])
                inventory_map[(s_id, v_id)] = inv

        # 7. Build items & calculate relevance score
        clean_q_lower = clean_q.lower()
        items: List[Tuple[SearchProductItem, int]] = []  # (item, relevance_score)

        for p in matched_products:
            pid = str(p["_id"])
            p_name = p.get("name", "")
            p_brand = p.get("brand") or ""
            p_keywords = p.get("searchKeywords") or []
            prod_variants = variants_by_product.get(pid, [])

            min_price_paise = None
            max_mrp_paise = None
            total_stock = 0
            has_stock = False
            variant_items: List[ProductVariantItem] = []

            for v in prod_variants:
                vid = str(v["_id"])
                v_price = None
                v_mrp = None
                v_avail_qty = None
                v_is_avail = None

                if eligible_shop_ids:
                    for sid in eligible_shop_ids:
                        inv = inventory_map.get((sid, vid))
                        if inv:
                            cur_price = inv.get("pricePaise", 0)
                            cur_mrp = inv.get("mrpPaise")
                            cur_qty = max(inv.get("stockQuantity", 0) - inv.get("reservedQuantity", 0), 0)
                            is_av = inv.get("isAvailable", True) and cur_qty > 0

                            if v_price is None or cur_price < v_price:
                                v_price = cur_price
                                v_mrp = cur_mrp
                                v_avail_qty = cur_qty
                                v_is_avail = is_av

                    if v_price is not None:
                        if min_price_paise is None or v_price < min_price_paise:
                            min_price_paise = v_price
                            max_mrp_paise = v_mrp
                        if v_avail_qty:
                            total_stock += v_avail_qty
                        if v_is_avail:
                            has_stock = True

                variant_items.append(
                    ProductVariantItem(
                        id=vid,
                        productId=pid,
                        variantName=v.get("variantName", ""),
                        packSize=float(v.get("packSize", 1.0)),
                        unit=v.get("unit", "piece"),
                        sku=v.get("sku", ""),
                        barcode=v.get("barcode"),
                        imageUrl=v.get("imageUrl"),
                        pricePaise=v_price,
                        mrpPaise=v_mrp,
                        availableQuantity=v_avail_qty,
                        isAvailable=v_is_avail,
                    )
                )

            # Filtering: in_stock
            if in_stock is not None:
                if in_stock is True and not has_stock:
                    continue
                if in_stock is False and has_stock:
                    continue

            # Filtering: min_price / max_price
            if min_price is not None:
                if min_price_paise is None or min_price_paise < min_price:
                    continue
            if max_price is not None:
                if min_price_paise is None or min_price_paise > max_price:
                    continue

            # Compute relevance score:
            # 1: Exact product name match
            # 2: Product name begins with query
            # 3: Product name contains query
            # 4: Brand match
            # 5: SKU match
            # 6: Search keywords / category match
            p_name_lower = p_name.lower()
            if p_name_lower == clean_q_lower:
                rel_score = 1
            elif p_name_lower.startswith(clean_q_lower):
                rel_score = 2
            elif clean_q_lower in p_name_lower:
                rel_score = 3
            elif clean_q_lower in p_brand.lower():
                rel_score = 4
            elif any(clean_q_lower in (v.get("sku", "")).lower() for v in prod_variants):
                rel_score = 5
            else:
                rel_score = 6

            cat_id_str = str(p.get("categoryId")) if p.get("categoryId") else None
            cat_obj = categories_map.get(cat_id_str) if cat_id_str else None

            price_obj = None
            if min_price_paise is not None:
                price_obj = ProductPrice(amountPaise=min_price_paise, mrpPaise=max_mrp_paise, currency="INR")

            avail_obj = ProductAvailabilitySummary(
                isAvailable=has_stock,
                availableQuantity=total_stock,
                reasonCode="AVAILABLE" if has_stock else "OUT_OF_STOCK",
            )

            item = SearchProductItem(
                id=pid,
                productId=pid,
                name=p_name,
                slug=p.get("slug", ""),
                imageUrl=p.get("imageUrl"),
                category=cat_obj,
                categoryId=cat_id_str,
                brand=p.get("brand"),
                price=price_obj,
                pricePaise=min_price_paise,
                inStock=has_stock,
                availability=avail_obj,
                variants=variant_items,
            )
            items.append((item, rel_score))

        # 8. Deterministic sorting
        if sort_by == "price_asc":
            items.sort(key=lambda x: (x[0].pricePaise is None, x[0].pricePaise or 0, x[0].id))
        elif sort_by == "price_desc":
            items.sort(key=lambda x: (x[0].pricePaise is None, -(x[0].pricePaise or 0), x[0].id))
        elif sort_by == "name_asc":
            items.sort(key=lambda x: (x[0].name.lower(), x[0].id))
        elif sort_by == "newest":
            items.sort(key=lambda x: x[0].id, reverse=True)
        else:  # relevance
            items.sort(key=lambda x: (x[1], x[0].name.lower(), x[0].id))

        total = len(items)
        offset = (page - 1) * limit
        totalPages = (total + limit - 1) // limit if total > 0 else 0
        hasMore = (offset + limit) < total
        paginated_items = [item[0] for item in items[offset : offset + limit]]

        # Record search event asynchronously for analytics
        await cls.record_search_event(clean_q, result_count=total)

        pagination = PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            page=page,
            totalPages=totalPages,
            hasMore=hasMore,
        )
        return paginated_items, pagination

    @classmethod
    async def get_suggestions(cls, q: str, limit: int = 10) -> List[SearchSuggestionItem]:
        """Return autocomplete suggestions across product names, categories, and brands."""
        clean_q = q.strip() if q else ""
        if len(clean_q) < 2:
            return []

        limit = min(max(limit, 1), 10)
        db = get_db()
        safe_q = re.escape(clean_q)
        suggestions: List[SearchSuggestionItem] = []
        seen_texts = set()

        # 1. Product names starting with query
        prefix_cursor = db.products.find(
            {"isActive": True, "name": {"$regex": f"^{safe_q}", "$options": "i"}},
            {"_id": 1, "name": 1, "imageUrl": 1},
        ).limit(limit)
        async for p in prefix_cursor:
            text = p.get("name", "").strip()
            if text and text.lower() not in seen_texts:
                seen_texts.add(text.lower())
                suggestions.append(SearchSuggestionItem(text=text, type="product", id=str(p["_id"]), imageUrl=p.get("imageUrl")))

        # 2. Product names containing query (if needed)
        if len(suggestions) < limit:
            remaining = limit - len(suggestions)
            contains_cursor = db.products.find(
                {"isActive": True, "name": {"$regex": safe_q, "$options": "i"}},
                {"_id": 1, "name": 1, "imageUrl": 1},
            ).limit(remaining * 2)
            async for p in contains_cursor:
                text = p.get("name", "").strip()
                if text and text.lower() not in seen_texts:
                    seen_texts.add(text.lower())
                    suggestions.append(SearchSuggestionItem(text=text, type="product", id=str(p["_id"]), imageUrl=p.get("imageUrl")))
                if len(suggestions) >= limit:
                    break

        # 3. Categories matching query
        if len(suggestions) < limit:
            remaining = limit - len(suggestions)
            cat_cursor = db.categories.find(
                {"isActive": True, "name": {"$regex": safe_q, "$options": "i"}},
                {"_id": 1, "name": 1, "imageUrl": 1},
            ).limit(remaining)
            async for c in cat_cursor:
                text = c.get("name", "").strip()
                if text and text.lower() not in seen_texts:
                    seen_texts.add(text.lower())
                    suggestions.append(SearchSuggestionItem(text=text, type="category", id=str(c["_id"]), imageUrl=c.get("imageUrl")))

        # 4. Brands matching query
        if len(suggestions) < limit:
            remaining = limit - len(suggestions)
            brands = await db.products.distinct("brand", {"isActive": True, "brand": {"$regex": safe_q, "$options": "i"}})
            for b in brands:
                if b and b.strip() and b.strip().lower() not in seen_texts:
                    seen_texts.add(b.strip().lower())
                    suggestions.append(SearchSuggestionItem(text=b.strip(), type="brand"))
                if len(suggestions) >= limit:
                    break

        return suggestions[:limit]

    @classmethod
    async def get_trending(cls, limit: int = 10, days: int = 7) -> List[TrendingSearchItem]:
        """Calculate and return trending search queries aggregated over the specified time window."""
        limit = min(max(limit, 1), 20)
        days = min(max(days, 1), 30)
        db = get_db()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        pipeline = [
            {
                "$match": {
                    "createdAt": {"$gte": cutoff},
                    "resultCount": {"$gt": 0},
                }
            },
            {
                "$group": {
                    "_id": "$normalizedQuery",
                    "searchCount": {"$sum": 1},
                    "displayQuery": {"$first": "$query"},
                }
            },
            {
                "$sort": {"searchCount": -1, "_id": 1}
            },
            {
                "$limit": limit
            },
            {
                "$project": {
                    "_id": 0,
                    "query": "$displayQuery",
                    "searchCount": 1,
                }
            },
        ]

        trending: List[TrendingSearchItem] = []
        try:
            cursor = db.search_events.aggregate(pipeline)
            async for doc in cursor:
                trending.append(TrendingSearchItem(query=doc["query"], searchCount=doc["searchCount"]))
        except Exception as exc:
            logger.warning(f"Error fetching trending searches: {exc}")

        return trending

    @classmethod
    async def record_search_event(cls, query: str, result_count: int, ip_address: Optional[str] = None) -> None:
        """Lightweight recording of a meaningful search query with deduplication and abuse protection."""
        if not query or len(query.strip()) < 2:
            return

        clean_q = query.strip()
        normalized = clean_q.lower()
        now = datetime.now(timezone.utc)
        db = get_db()

        try:
            # Abuse protection / deduplication: avoid recording exact duplicate within 15 seconds
            fifteen_sec_ago = now - timedelta(seconds=15)
            recent_duplicate = await db.search_events.find_one({
                "normalizedQuery": normalized,
                "createdAt": {"$gte": fifteen_sec_ago},
            })
            if recent_duplicate:
                return

            await db.search_events.insert_one({
                "query": clean_q,
                "normalizedQuery": normalized,
                "resultCount": result_count,
                "ipAddress": ip_address,
                "createdAt": now,
            })
        except Exception as exc:
            logger.warning(f"Could not record search event: {exc}")
