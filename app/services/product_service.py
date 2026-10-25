import re
from typing import Any, Dict, List, Optional, Tuple, Union
from bson import ObjectId
from app.core.exceptions import BadRequestException, NotFoundException
from app.db.mongodb import get_db
from app.schemas.product import (
    PaginationMeta,
    ProductAvailabilityResponseData,
    ProductAvailabilitySummary,
    ProductDetailResponseData,
    ProductListItem,
    ProductListResponseData,
    ProductPrice,
)
from app.schemas.variant import ProductVariantItem
from app.services.shop_service import ShopService


class ProductService:
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
    async def get_eligible_shop_ids(
        cls,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
    ) -> List[str]:
        """Resolve a list of eligible shop IDs based on shopId or serviceAreaId."""
        db = get_db()
        if shop_id:
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

        return []

    @classmethod
    async def list_products(
        cls,
        q: Optional[str] = None,
        category_id: Optional[str] = None,
        subcategory_id: Optional[str] = None,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
        brand: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        in_stock_only: bool = False,
        in_stock: Optional[bool] = None,
        featured_only: bool = False,
        sort: str = "relevance",
        sort_by: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[ProductListItem], int]:
        db = get_db()
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)

        # Validation
        chosen_sort = (sort_by or sort or "relevance").strip().lower()
        valid_sorts = {"relevance", "price_asc", "price_desc", "name_asc", "newest"}
        if chosen_sort not in valid_sorts:
            raise BadRequestException(
                f"Unsupported sort value '{chosen_sort}'. Supported values: relevance, price_asc, price_desc, name_asc, newest.",
                code="UNSUPPORTED_SORT",
            )
        sort = chosen_sort

        if min_price is not None and min_price < 0:
            raise BadRequestException("minPrice cannot be negative.", code="INVALID_PRICE")
        if max_price is not None and max_price < 0:
            raise BadRequestException("maxPrice cannot be negative.", code="INVALID_PRICE")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise BadRequestException("minPrice cannot be greater than maxPrice.", code="INVALID_PRICE_RANGE")

        if category_id:
            clean_cat = category_id.strip()
            if not clean_cat:
                raise BadRequestException("Invalid categoryId format.", code="INVALID_CATEGORY_ID")
            if not ObjectId.is_valid(clean_cat) and not re.match(r"^[a-zA-Z0-9_-]{3,50}$", clean_cat):
                raise BadRequestException("Invalid categoryId format.", code="INVALID_CATEGORY_ID")

        if shop_id:
            clean_shop = shop_id.strip()
            if not clean_shop:
                raise BadRequestException("Invalid shopId format.", code="INVALID_SHOP_ID")
            if not ObjectId.is_valid(clean_shop) and not re.match(r"^[a-zA-Z0-9_-]{3,50}$", clean_shop):
                raise BadRequestException("Invalid shopId format.", code="INVALID_SHOP_ID")

        # Base product query: must be active
        query: dict = {"isActive": True}

        if featured_only:
            query["isFeatured"] = True

        if category_id:
            cat_obj_id = cls._to_object_id(category_id)
            query["categoryId"] = {"$in": [cat_obj_id, category_id]} if cat_obj_id else category_id

        if subcategory_id:
            subcat_obj_id = cls._to_object_id(subcategory_id)
            query["subcategoryId"] = {"$in": [subcat_obj_id, subcategory_id]} if subcat_obj_id else subcategory_id

        if brand:
            query["brand"] = {"$regex": f"^{re.escape(brand.strip())}$", "$options": "i"}

        if q and q.strip():
            safe_q = re.escape(q.strip())
            query["$or"] = [
                {"name": {"$regex": safe_q, "$options": "i"}},
                {"brand": {"$regex": safe_q, "$options": "i"}},
                {"searchKeywords": {"$regex": safe_q, "$options": "i"}},
            ]

        # Resolve eligible shops
        eligible_shop_ids = await cls.get_eligible_shop_ids(shop_id, service_area_id)
        if not eligible_shop_ids and (shop_id is None and service_area_id is None):
            # Resolve active shops for catalogue pricing & availability
            cursor_s = db.shops.find({"isActive": True})
            async for s in cursor_s:
                eligible_shop_ids.append(str(s["_id"]))
        has_shop_context = bool(eligible_shop_ids)

        # Fetch products matching catalogue query
        cursor = db.products.find(query)
        matched_products = []
        async for p in cursor:
            matched_products.append(p)

        if not matched_products:
            return [], 0

        product_ids = [p["_id"] for p in matched_products]
        p_id_strs = [str(pid) for pid in product_ids]
        combined_p_ids = list(set(product_ids + p_id_strs))

        # Fetch active variants for these products
        variants_cursor = db.product_variants.find(
            {"productId": {"$in": combined_p_ids}, "isActive": True}
        ).sort([("packSize", 1)])
        variants_by_product: dict = {}
        all_variant_ids = []
        async for v in variants_cursor:
            pid = str(v.get("productId"))
            vid = str(v["_id"])
            all_variant_ids.append(v["_id"])
            all_variant_ids.append(vid)
            variants_by_product.setdefault(pid, []).append(v)

        # If shop context exists, fetch inventory
        inventory_map: dict = {}  # (shop_id, variant_id) -> inventory_doc
        if has_shop_context and all_variant_ids:
            inv_query: dict = {
                "shopId": {"$in": eligible_shop_ids + [cls._to_object_id(sid) for sid in eligible_shop_ids if cls._to_object_id(sid)]},
                "variantId": {"$in": all_variant_ids},
            }
            inv_cursor = db.shop_inventory.find(inv_query)
            async for inv in inv_cursor:
                s_id = str(inv["shopId"])
                v_id = str(inv["variantId"])
                inventory_map[(s_id, v_id)] = inv

        # Build items
        items: List[ProductListItem] = []
        for p in matched_products:
            pid = str(p["_id"])
            prod_variants = variants_by_product.get(pid, [])

            price_obj: Optional[ProductPrice] = None
            avail_obj: Optional[ProductAvailabilitySummary] = None
            variant_items: List[ProductVariantItem] = []

            min_price_paise = None
            max_mrp_paise = None
            total_stock = 0
            has_stock = False

            for v in prod_variants:
                vid = str(v["_id"])
                v_price = None
                v_mrp = None
                v_avail_qty = None
                v_is_avail = None

                if has_shop_context:
                    # Find inventory in eligible shop(s)
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

            if has_shop_context and min_price_paise is not None:
                price_obj = ProductPrice(amountPaise=min_price_paise, mrpPaise=max_mrp_paise, currency="INR")
                avail_obj = ProductAvailabilitySummary(
                    isAvailable=has_stock,
                    availableQuantity=total_stock,
                    reasonCode="AVAILABLE" if has_stock else "OUT_OF_STOCK",
                )

            # Filtering: in_stock
            if in_stock is not None:
                if in_stock is True and not has_stock:
                    continue
                if in_stock is False and has_stock:
                    continue
            elif in_stock_only and not has_stock:
                continue

            # Filtering: min_price / max_price
            if min_price is not None:
                if min_price_paise is None or min_price_paise < min_price:
                    continue
            if max_price is not None:
                if min_price_paise is None or min_price_paise > max_price:
                    continue

            items.append(
                ProductListItem(
                    id=pid,
                    name=p.get("name", ""),
                    slug=p.get("slug", ""),
                    brand=p.get("brand"),
                    categoryId=str(p.get("categoryId")),
                    subcategoryId=str(p.get("subcategoryId")) if p.get("subcategoryId") else None,
                    imageUrl=p.get("imageUrl"),
                    price=price_obj,
                    availability=avail_obj,
                    variants=variant_items,
                )
            )

        # Deterministic in-memory sorting
        if sort == "price_asc":
            items.sort(key=lambda x: (x.price.amountPaise is None if x.price else True, x.price.amountPaise if x.price else 0, x.id))
        elif sort == "price_desc":
            items.sort(key=lambda x: (x.price.amountPaise is None if x.price else True, -(x.price.amountPaise) if x.price else 0, x.id))
        elif sort == "name_asc":
            items.sort(key=lambda x: (x.name.lower(), x.id))
        elif sort == "newest":
            items.sort(key=lambda x: x.id, reverse=True)
        else:
            items.sort(key=lambda x: x.id)

        total = len(items)
        paginated_items = items[offset : offset + limit]
        return paginated_items, total

    @classmethod
    async def get_product_by_id(
        cls,
        product_id: str,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
    ) -> ProductDetailResponseData:
        db = get_db()
        obj_id = cls._to_object_id(product_id)
        query = {"$or": [{"_id": obj_id}, {"_id": product_id}]} if obj_id else {"_id": product_id}
        doc = await db.products.find_one(query)

        if not doc or not doc.get("isActive", True):
            raise NotFoundException("Product not found or inactive.", code="PRODUCT_NOT_FOUND")

        pid = str(doc["_id"])
        p_obj_id = cls._to_object_id(pid)
        p_variants = [p_obj_id, pid] if p_obj_id else [pid]

        # Fetch variants
        v_cursor = db.product_variants.find({"productId": {"$in": p_variants}, "isActive": True}).sort([("packSize", 1)])
        variants = []
        async for v in v_cursor:
            variants.append(v)

        eligible_shop_ids = await cls.get_eligible_shop_ids(shop_id, service_area_id)
        has_shop_context = bool(eligible_shop_ids)

        inventory_map: dict = {}
        if has_shop_context and variants:
            v_ids = [v["_id"] for v in variants] + [str(v["_id"]) for v in variants]
            inv_query: dict = {
                "shopId": {"$in": eligible_shop_ids + [cls._to_object_id(sid) for sid in eligible_shop_ids if cls._to_object_id(sid)]},
                "variantId": {"$in": v_ids},
            }
            inv_cursor = db.shop_inventory.find(inv_query)
            async for inv in inv_cursor:
                inventory_map[(str(inv["shopId"]), str(inv["variantId"]))] = inv

        variant_items: List[ProductVariantItem] = []
        min_price_paise = None
        max_mrp_paise = None
        total_stock = 0
        has_stock = False

        for v in variants:
            vid = str(v["_id"])
            v_price = None
            v_mrp = None
            v_avail_qty = None
            v_is_avail = None

            if has_shop_context:
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

        price_obj = None
        avail_obj = None
        selected_shop_info = None

        if has_shop_context:
            if min_price_paise is not None:
                price_obj = ProductPrice(amountPaise=min_price_paise, mrpPaise=max_mrp_paise, currency="INR")
                avail_obj = ProductAvailabilitySummary(
                    isAvailable=has_stock,
                    availableQuantity=total_stock,
                    reasonCode="AVAILABLE" if has_stock else "OUT_OF_STOCK",
                )
            if shop_id:
                s_obj_id = cls._to_object_id(shop_id)
                s_doc = await db.shops.find_one({"$or": [{"_id": s_obj_id}, {"_id": shop_id}]} if s_obj_id else {"_id": shop_id})
                if s_doc:
                    is_open, _ = ShopService.calculate_is_open(s_doc)
                    selected_shop_info = {
                        "id": str(s_doc["_id"]),
                        "name": s_doc.get("name"),
                        "isOpen": is_open,
                        "acceptsOrders": s_doc.get("acceptsOrders", True),
                    }

        return ProductDetailResponseData(
            id=pid,
            name=doc.get("name", ""),
            slug=doc.get("slug", ""),
            shortDescription=doc.get("shortDescription"),
            description=doc.get("description"),
            brand=doc.get("brand"),
            categoryId=str(doc.get("categoryId")),
            subcategoryId=str(doc.get("subcategoryId")) if doc.get("subcategoryId") else None,
            imageUrl=doc.get("imageUrl"),
            images=doc.get("images", []),
            variants=variant_items,
            selectedShop=selected_shop_info,
            price=price_obj,
            availability=avail_obj,
        )

    @classmethod
    async def get_product_variants(
        cls,
        product_id: str,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
    ) -> List[ProductVariantItem]:
        # Validate product
        await cls.get_product_by_id(product_id)

        db = get_db()
        p_obj_id = cls._to_object_id(product_id)
        p_variants = [p_obj_id, product_id] if p_obj_id else [product_id]

        v_cursor = db.product_variants.find({"productId": {"$in": p_variants}, "isActive": True}).sort([("packSize", 1)])
        variants = []
        async for v in v_cursor:
            variants.append(v)

        eligible_shop_ids = await cls.get_eligible_shop_ids(shop_id, service_area_id)
        has_shop_context = bool(eligible_shop_ids)

        inventory_map: dict = {}
        if has_shop_context and variants:
            v_ids = [v["_id"] for v in variants] + [str(v["_id"]) for v in variants]
            inv_query: dict = {
                "shopId": {"$in": eligible_shop_ids + [cls._to_object_id(sid) for sid in eligible_shop_ids if cls._to_object_id(sid)]},
                "variantId": {"$in": v_ids},
            }
            inv_cursor = db.shop_inventory.find(inv_query)
            async for inv in inv_cursor:
                inventory_map[(str(inv["shopId"]), str(inv["variantId"]))] = inv

        items: List[ProductVariantItem] = []
        for v in variants:
            vid = str(v["_id"])
            v_price = None
            v_mrp = None
            v_avail_qty = None
            v_is_avail = None

            if has_shop_context:
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

            items.append(
                ProductVariantItem(
                    id=vid,
                    productId=product_id,
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

        return items

    @classmethod
    async def check_product_availability(
        cls,
        product_id: str,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
        variant_id: Optional[str] = None,
    ) -> ProductAvailabilityResponseData:
        db = get_db()
        obj_id = cls._to_object_id(product_id)
        query = {"$or": [{"_id": obj_id}, {"_id": product_id}]} if obj_id else {"_id": product_id}
        doc = await db.products.find_one(query)

        if not doc:
            raise NotFoundException("Product not found.", code="PRODUCT_NOT_FOUND")

        if not doc.get("isActive", True):
            return ProductAvailabilityResponseData(
                productId=product_id,
                shopId=shop_id,
                variantId=variant_id,
                isAvailable=False,
                availableQuantity=0,
                reasonCode="PRODUCT_INACTIVE",
            )

        if not shop_id and not service_area_id:
            raise BadRequestException("Either shopId or serviceAreaId must be provided to check availability.")

        eligible_shop_ids = await cls.get_eligible_shop_ids(shop_id, service_area_id)
        if not eligible_shop_ids:
            return ProductAvailabilityResponseData(
                productId=product_id,
                shopId=shop_id,
                variantId=variant_id,
                isAvailable=False,
                availableQuantity=0,
                reasonCode="SHOP_NOT_SERVICEABLE",
            )

        # Check shop hours for the selected shop
        target_shop_id = eligible_shop_ids[0]
        s_obj = cls._to_object_id(target_shop_id)
        shop_doc = await db.shops.find_one({"$or": [{"_id": s_obj}, {"_id": target_shop_id}]} if s_obj else {"_id": target_shop_id})
        if not shop_doc or not shop_doc.get("isActive", True):
            return ProductAvailabilityResponseData(
                productId=product_id,
                shopId=target_shop_id,
                variantId=variant_id,
                isAvailable=False,
                availableQuantity=0,
                reasonCode="SHOP_INACTIVE",
            )

        is_open, _ = ShopService.calculate_is_open(shop_doc)
        if not is_open:
            return ProductAvailabilityResponseData(
                productId=product_id,
                shopId=target_shop_id,
                variantId=variant_id,
                isAvailable=False,
                availableQuantity=0,
                reasonCode="SHOP_CLOSED",
            )

        if not shop_doc.get("acceptsOrders", True):
            return ProductAvailabilityResponseData(
                productId=product_id,
                shopId=target_shop_id,
                variantId=variant_id,
                isAvailable=False,
                availableQuantity=0,
                reasonCode="SHOP_NOT_ACCEPTING_ORDERS",
            )

        # Check variant
        if variant_id:
            v_obj = cls._to_object_id(variant_id)
            v_doc = await db.product_variants.find_one(
                {"$or": [{"_id": v_obj}, {"_id": variant_id}]} if v_obj else {"_id": variant_id}
            )
            if not v_doc or not v_doc.get("isActive", True):
                return ProductAvailabilityResponseData(
                    productId=product_id,
                    shopId=target_shop_id,
                    variantId=variant_id,
                    isAvailable=False,
                    availableQuantity=0,
                    reasonCode="VARIANT_INACTIVE",
                )

            # Check inventory
            s_variants = [s_obj, target_shop_id] if s_obj else [target_shop_id]
            v_variants = [v_obj, variant_id] if v_obj else [variant_id]
            inv_doc = await db.shop_inventory.find_one({
                "shopId": {"$in": s_variants},
                "variantId": {"$in": v_variants},
            })

            if not inv_doc:
                return ProductAvailabilityResponseData(
                    productId=product_id,
                    shopId=target_shop_id,
                    variantId=variant_id,
                    isAvailable=False,
                    availableQuantity=0,
                    reasonCode="INVENTORY_NOT_CONFIGURED",
                )

            avail_qty = max(inv_doc.get("stockQuantity", 0) - inv_doc.get("reservedQuantity", 0), 0)
            is_avail = inv_doc.get("isAvailable", True) and avail_qty > 0

            return ProductAvailabilityResponseData(
                productId=product_id,
                shopId=target_shop_id,
                variantId=variant_id,
                isAvailable=is_avail,
                availableQuantity=avail_qty,
                pricePaise=inv_doc.get("pricePaise"),
                mrpPaise=inv_doc.get("mrpPaise"),
                currency="INR",
                reasonCode="AVAILABLE" if is_avail else "OUT_OF_STOCK",
            )

        # No specific variant: evaluate across all active variants
        p_obj_id = cls._to_object_id(product_id)
        p_variants = [p_obj_id, product_id] if p_obj_id else [product_id]
        v_cursor = db.product_variants.find({"productId": {"$in": p_variants}, "isActive": True})
        v_ids = []
        async for v in v_cursor:
            v_ids.append(v["_id"])
            v_ids.append(str(v["_id"]))

        if not v_ids:
            return ProductAvailabilityResponseData(
                productId=product_id,
                shopId=target_shop_id,
                isAvailable=False,
                availableQuantity=0,
                reasonCode="OUT_OF_STOCK",
            )

        s_variants = [s_obj, target_shop_id] if s_obj else [target_shop_id]
        inv_cursor = db.shop_inventory.find({
            "shopId": {"$in": s_variants},
            "variantId": {"$in": v_ids},
        })

        total_qty = 0
        min_p = None
        mrp_p = None
        has_any_avail = False
        async for inv in inv_cursor:
            q = max(inv.get("stockQuantity", 0) - inv.get("reservedQuantity", 0), 0)
            if inv.get("isAvailable", True) and q > 0:
                has_any_avail = True
                total_qty += q
                p_paise = inv.get("pricePaise", 0)
                if min_p is None or p_paise < min_p:
                    min_p = p_paise
                    mrp_p = inv.get("mrpPaise")

        return ProductAvailabilityResponseData(
            productId=product_id,
            shopId=target_shop_id,
            isAvailable=has_any_avail,
            availableQuantity=total_qty,
            pricePaise=min_p,
            mrpPaise=mrp_p,
            currency="INR",
            reasonCode="AVAILABLE" if has_any_avail else "OUT_OF_STOCK",
        )

    @classmethod
    async def get_related_products(
        cls,
        product_id: str,
        shop_id: Optional[str] = None,
        service_area_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[ProductListItem]:
        # Validate product
        orig_prod = await cls.get_product_by_id(product_id)

        db = get_db()
        limit = min(max(limit, 1), 20)

        # Related criteria: same category or brand, excluding current product
        p_obj_id = cls._to_object_id(product_id)
        exclude_variants = [p_obj_id, product_id] if p_obj_id else [product_id]

        query: dict = {
            "isActive": True,
            "_id": {"$nin": exclude_variants},
        }

        # Match category or brand
        match_conditions = []
        if orig_prod.categoryId:
            cat_obj = cls._to_object_id(orig_prod.categoryId)
            match_conditions.append({"categoryId": {"$in": [cat_obj, orig_prod.categoryId]} if cat_obj else orig_prod.categoryId})
        if orig_prod.brand:
            match_conditions.append({"brand": orig_prod.brand})

        if match_conditions:
            query["$or"] = match_conditions

        items, _ = await cls.list_products(
            category_id=orig_prod.categoryId,
            shop_id=shop_id,
            service_area_id=service_area_id,
            limit=limit,
        )

        # Filter out the original product
        filtered = [item for item in items if item.id != product_id]
        return filtered[:limit]
