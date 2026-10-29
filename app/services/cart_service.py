from datetime import datetime, timezone
import secrets
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.logging import logger
from app.db.mongodb import get_db
from app.schemas.cart import (
    CartItemResponse,
    CartResponseData,
    CartValidationItem,
    CartValidationResponseData,
    GuestCartMergeResponseData,
)


class CartService:
    MAX_QUANTITY_PER_ITEM = 50

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
    async def resolve_shop(
        cls,
        customer_id: Optional[str] = None,
        shop_id: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[dict]]:
        """
        Resolve the shop context.
        1. If shop_id provided, validate and return.
        2. If customer_id provided, check customer's default address for supported shops.
        3. Fallback to the active primary store.
        """
        db = get_db()
        if shop_id:
            s_obj_id = cls._to_object_id(shop_id)
            query = {"$or": [{"_id": s_obj_id}, {"_id": shop_id}]} if s_obj_id else {"_id": shop_id}
            shop = await db.shops.find_one(query)
            if not shop or not shop.get("isActive", True):
                raise BadRequestException("Specified shop is invalid or inactive.", code="SHOP_NOT_FOUND")
            return str(shop["_id"]), shop

        # Check customer default address
        if customer_id:
            c_obj_id = cls._to_object_id(customer_id)
            addr_query = {
                "customerId": {"$in": [customer_id, c_obj_id] if c_obj_id else [customer_id]},
                "isDefault": True,
            }
            address = await db.addresses.find_one(addr_query)
            if address and address.get("postalCode"):
                pincode = str(address["postalCode"]).strip()
                shop = await db.shops.find_one({
                    "isActive": True,
                    "supportedPostalCodes": pincode,
                })
                if shop:
                    return str(shop["_id"]), shop

        # Fallback to default active launch shop
        shop = await db.shops.find_one({"isActive": True, "acceptsOrders": True})
        if shop:
            return str(shop["_id"]), shop

        # Any active shop
        shop = await db.shops.find_one({"isActive": True})
        if shop:
            return str(shop["_id"]), shop

        return None, None

    @classmethod
    async def get_or_create_customer_cart(
        cls,
        customer_id: str,
        shop_id: Optional[str] = None,
    ) -> dict:
        """Fetch or create active cart document for the authenticated customer."""
        db = get_db()
        cart = await db.carts.find_one({"customerId": customer_id, "status": "active"})
        if cart:
            if shop_id and not cart.get("shopId"):
                await db.carts.update_one({"_id": cart["_id"]}, {"$set": {"shopId": shop_id}})
                cart["shopId"] = shop_id
            return cart

        resolved_shop_id, _ = await cls.resolve_shop(customer_id=customer_id, shop_id=shop_id)
        now = datetime.now(timezone.utc)
        new_cart = {
            "_id": ObjectId(),
            "customerId": customer_id,
            "guestCartId": None,
            "shopId": resolved_shop_id,
            "status": "active",
            "items": [],
            "createdAt": now,
            "updatedAt": now,
        }
        try:
            await db.carts.insert_one(new_cart)
            return new_cart
        except DuplicateKeyError:
            # Concurrently created
            cart = await db.carts.find_one({"customerId": customer_id, "status": "active"})
            if cart:
                return cart
            raise

    @classmethod
    async def get_cart_document(cls, customer_id: str) -> Optional[dict]:
        """Fetch active cart document for a customer without auto-creating."""
        db = get_db()
        return await db.carts.find_one({"customerId": customer_id, "status": "active"})

    @classmethod
    async def get_enriched_cart(cls, cart_doc: dict) -> CartResponseData:
        """
        Enrich raw cart document items with trusted product, variant, and live shop inventory data.
        Always calculates subtotals server-side and checks for stock/availability warnings.
        """
        db = get_db()
        items_raw = cart_doc.get("items", [])
        cart_id = str(cart_doc["_id"])
        customer_id = cart_doc.get("customerId")
        guest_cart_id = cart_doc.get("guestCartId")
        shop_id = cart_doc.get("shopId")
        updated_at = cart_doc.get("updatedAt")

        if not items_raw:
            return CartResponseData(
                cartId=cart_id,
                customerId=customer_id,
                guestCartId=guest_cart_id,
                shopId=shop_id,
                items=[],
                subtotalPaise=0,
                subtotal=0.0,
                currency="INR",
                itemCount=0,
                totalQuantity=0,
                warnings=[],
                updatedAt=updated_at,
            )

        # Bulk fetch products & variants
        prod_ids = [cls._to_object_id(it.get("productId")) or it.get("productId") for it in items_raw]
        var_ids = [cls._to_object_id(it.get("variantId")) or it.get("variantId") for it in items_raw]

        products_map: Dict[str, dict] = {}
        async for p in db.products.find({"_id": {"$in": prod_ids}}):
            products_map[str(p["_id"])] = p

        variants_map: Dict[str, dict] = {}
        async for v in db.product_variants.find({"_id": {"$in": var_ids}}):
            variants_map[str(v["_id"])] = v

        # Fetch shop inventory
        inventory_map: Dict[str, dict] = {}
        if shop_id:
            s_obj_id = cls._to_object_id(shop_id)
            shop_query_ids = [shop_id, s_obj_id] if s_obj_id else [shop_id]
            inv_cursor = db.shop_inventory.find({
                "shopId": {"$in": shop_query_ids},
                "variantId": {"$in": var_ids},
            })
            async for inv in inv_cursor:
                inventory_map[str(inv["variantId"])] = inv

        enriched_items: List[CartItemResponse] = []
        total_subtotal_paise = 0
        total_qty = 0
        warnings: List[str] = []

        for it in items_raw:
            item_id = str(it.get("itemId", ""))
            pid = str(it.get("productId", ""))
            vid = str(it.get("variantId", ""))
            qty = int(it.get("quantity", 1))

            product = products_map.get(pid)
            variant = variants_map.get(vid)
            inv = inventory_map.get(vid)

            p_name = product.get("name", "Product Unavailable") if product else "Product Unavailable"
            p_img = product.get("imageUrl") if product else None
            v_name = variant.get("variantName", "Variant Unavailable") if variant else "Variant Unavailable"
            pack_size = float(variant.get("packSize", 1.0)) if variant else 1.0
            unit = variant.get("unit", "piece") if variant else "piece"

            # Determine price from shop_inventory or fallback
            unit_price_paise = 0
            if inv and inv.get("pricePaise") is not None:
                unit_price_paise = int(inv["pricePaise"])
            elif variant and variant.get("pricePaise") is not None:
                unit_price_paise = int(variant["pricePaise"])
            elif it.get("priceSnapshotPaise") is not None:
                unit_price_paise = int(it["priceSnapshotPaise"])

            # Determine stock
            stock_qty = 0
            is_avail = False
            if inv:
                stock_qty = max(inv.get("stockQuantity", 0) - inv.get("reservedQuantity", 0), 0)
                is_avail = inv.get("isAvailable", True) and (stock_qty >= qty)
            elif variant:
                is_avail = variant.get("isActive", True)
                stock_qty = 10 if is_avail else 0

            # Active checks
            if not product or not product.get("isActive", True):
                is_avail = False
                warnings.append(f"'{p_name}' is no longer available.")
            elif not variant or not variant.get("isActive", True):
                is_avail = False
                warnings.append(f"'{p_name} ({v_name})' variant is no longer available.")
            elif stock_qty == 0:
                is_avail = False
                warnings.append(f"'{p_name} ({v_name})' is currently out of stock.")
            elif stock_qty < qty:
                is_avail = False
                warnings.append(f"'{p_name} ({v_name})' only has {stock_qty} in stock (requested {qty}).")

            item_subtotal_paise = unit_price_paise * qty
            total_subtotal_paise += item_subtotal_paise
            total_qty += qty

            enriched_items.append(
                CartItemResponse(
                    itemId=item_id,
                    productId=pid,
                    productName=p_name,
                    imageUrl=p_img,
                    variantId=vid,
                    variantName=v_name,
                    packSize=pack_size,
                    unit=unit,
                    quantity=qty,
                    unitPricePaise=unit_price_paise,
                    unitPrice=round(unit_price_paise / 100.0, 2),
                    subtotalPaise=item_subtotal_paise,
                    subtotal=round(item_subtotal_paise / 100.0, 2),
                    inStock=is_avail,
                    availableQuantity=stock_qty,
                )
            )

        return CartResponseData(
            cartId=cart_id,
            customerId=customer_id,
            guestCartId=guest_cart_id,
            shopId=shop_id,
            items=enriched_items,
            subtotalPaise=total_subtotal_paise,
            subtotal=round(total_subtotal_paise / 100.0, 2),
            currency="INR",
            itemCount=len(enriched_items),
            totalQuantity=total_qty,
            warnings=warnings,
            updatedAt=updated_at,
        )

    @classmethod
    async def get_cart(cls, customer_id: str) -> CartResponseData:
        """Fetch current authenticated customer's cart or return an empty cart."""
        cart = await cls.get_cart_document(customer_id)
        if not cart:
            return CartResponseData(
                cartId=f"empty_{customer_id}",
                customerId=customer_id,
                items=[],
                subtotalPaise=0,
                subtotal=0.0,
                currency="INR",
                itemCount=0,
                totalQuantity=0,
                warnings=[],
            )
        return await cls.get_enriched_cart(cart)

    @classmethod
    async def add_item(
        cls,
        customer_id: str,
        product_id: str,
        variant_id: str,
        quantity: int,
        shop_id: Optional[str] = None,
    ) -> CartResponseData:
        """Add product variant to cart or increment quantity if already present."""
        if quantity <= 0:
            raise BadRequestException("Quantity must be a positive integer.", code="INVALID_QUANTITY")
        if quantity > cls.MAX_QUANTITY_PER_ITEM:
            raise BadRequestException(f"Quantity cannot exceed {cls.MAX_QUANTITY_PER_ITEM}.", code="MAX_QUANTITY_EXCEEDED")

        db = get_db()
        p_obj_id = cls._to_object_id(product_id)
        p_query = {"$or": [{"_id": p_obj_id}, {"_id": product_id}]} if p_obj_id else {"_id": product_id}
        product = await db.products.find_one(p_query)
        if not product or not product.get("isActive", True):
            raise NotFoundException("Product not found or inactive.", code="PRODUCT_NOT_FOUND")

        v_obj_id = cls._to_object_id(variant_id)
        v_query = {"$or": [{"_id": v_obj_id}, {"_id": variant_id}]} if v_obj_id else {"_id": variant_id}
        variant = await db.product_variants.find_one(v_query)
        if not variant or not variant.get("isActive", True):
            raise NotFoundException("Variant not found or inactive.", code="VARIANT_NOT_FOUND")

        # Verify variant belongs to product
        variant_prod_id = str(variant.get("productId", ""))
        actual_prod_id = str(product["_id"])
        if variant_prod_id != actual_prod_id:
            raise BadRequestException("Variant does not belong to the specified product.", code="VARIANT_MISMATCH")

        # Get or create customer cart
        cart = await cls.get_or_create_customer_cart(customer_id, shop_id=shop_id)
        effective_shop_id = cart.get("shopId") or shop_id
        if not effective_shop_id:
            effective_shop_id, _ = await cls.resolve_shop(customer_id=customer_id)

        # Check inventory and price from shop_inventory
        price_paise = variant.get("pricePaise", 0)
        available_stock = 999
        if effective_shop_id:
            s_obj_id = cls._to_object_id(effective_shop_id)
            shop_query_ids = [effective_shop_id, s_obj_id] if s_obj_id else [effective_shop_id]
            inv = await db.shop_inventory.find_one({
                "shopId": {"$in": shop_query_ids},
                "variantId": {"$in": [variant_id, v_obj_id] if v_obj_id else [variant_id]},
            })
            if inv:
                price_paise = inv.get("pricePaise", price_paise)
                available_stock = max(inv.get("stockQuantity", 0) - inv.get("reservedQuantity", 0), 0)
                if not inv.get("isAvailable", True) or available_stock <= 0:
                    raise BadRequestException("Product variant is currently out of stock.", code="OUT_OF_STOCK")

        items: List[dict] = cart.get("items", [])
        now = datetime.now(timezone.utc)

        # Check if item already exists
        found = False
        for item in items:
            if str(item.get("variantId")) == str(variant["_id"]):
                new_qty = item.get("quantity", 0) + quantity
                if new_qty > cls.MAX_QUANTITY_PER_ITEM:
                    raise BadRequestException(
                        f"Cannot add {quantity}. Total cart quantity would exceed maximum limit of {cls.MAX_QUANTITY_PER_ITEM}.",
                        code="MAX_QUANTITY_EXCEEDED",
                    )
                if new_qty > available_stock:
                    raise BadRequestException(
                        f"Requested quantity ({new_qty}) exceeds available stock ({available_stock}).",
                        code="INSUFFICIENT_STOCK",
                    )
                item["quantity"] = new_qty
                item["priceSnapshotPaise"] = price_paise
                item["updatedAt"] = now
                found = True
                break

        if not found:
            if quantity > available_stock:
                raise BadRequestException(
                    f"Requested quantity ({quantity}) exceeds available stock ({available_stock}).",
                    code="INSUFFICIENT_STOCK",
                )
            items.append({
                "itemId": str(uuid.uuid4()),
                "productId": str(product["_id"]),
                "variantId": str(variant["_id"]),
                "quantity": quantity,
                "priceSnapshotPaise": price_paise,
                "createdAt": now,
                "updatedAt": now,
            })

        await db.carts.update_one(
            {"_id": cart["_id"]},
            {"$set": {"items": items, "shopId": effective_shop_id, "updatedAt": now}},
        )

        cart["items"] = items
        cart["shopId"] = effective_shop_id
        cart["updatedAt"] = now
        return await cls.get_enriched_cart(cart)

    @classmethod
    async def update_item_quantity(
        cls,
        customer_id: str,
        item_id: str,
        quantity: int,
    ) -> CartResponseData:
        """Update the quantity of a specific item in the customer's cart."""
        if quantity <= 0:
            raise BadRequestException("Quantity must be greater than zero. To remove the item, use the delete endpoint.", code="INVALID_QUANTITY")
        if quantity > cls.MAX_QUANTITY_PER_ITEM:
            raise BadRequestException(f"Quantity cannot exceed {cls.MAX_QUANTITY_PER_ITEM}.", code="MAX_QUANTITY_EXCEEDED")

        db = get_db()
        cart = await cls.get_cart_document(customer_id)
        if not cart or not cart.get("items"):
            raise NotFoundException("Cart item not found.", code="ITEM_NOT_FOUND")

        items: List[dict] = cart.get("items", [])
        target_item = None
        for it in items:
            if it.get("itemId") == item_id:
                target_item = it
                break

        if not target_item:
            raise NotFoundException("Cart item not found in customer cart.", code="ITEM_NOT_FOUND")

        # Recheck inventory
        shop_id = cart.get("shopId")
        variant_id = target_item.get("variantId")
        v_obj_id = cls._to_object_id(variant_id)
        available_stock = 999
        price_paise = target_item.get("priceSnapshotPaise", 0)

        if shop_id:
            s_obj_id = cls._to_object_id(shop_id)
            shop_query_ids = [shop_id, s_obj_id] if s_obj_id else [shop_id]
            inv = await db.shop_inventory.find_one({
                "shopId": {"$in": shop_query_ids},
                "variantId": {"$in": [variant_id, v_obj_id] if v_obj_id else [variant_id]},
            })
            if inv:
                price_paise = inv.get("pricePaise", price_paise)
                available_stock = max(inv.get("stockQuantity", 0) - inv.get("reservedQuantity", 0), 0)
                if not inv.get("isAvailable", True) or available_stock <= 0:
                    raise BadRequestException("Product variant is currently out of stock.", code="OUT_OF_STOCK")

        if quantity > available_stock:
            raise BadRequestException(
                f"Requested quantity ({quantity}) exceeds available stock ({available_stock}).",
                code="INSUFFICIENT_STOCK",
            )

        now = datetime.now(timezone.utc)
        target_item["quantity"] = quantity
        target_item["priceSnapshotPaise"] = price_paise
        target_item["updatedAt"] = now

        await db.carts.update_one(
            {"_id": cart["_id"]},
            {"$set": {"items": items, "updatedAt": now}},
        )

        cart["items"] = items
        cart["updatedAt"] = now
        return await cls.get_enriched_cart(cart)

    @classmethod
    async def remove_item(cls, customer_id: str, item_id: str) -> CartResponseData:
        """Remove a single item from the authenticated customer's cart."""
        db = get_db()
        cart = await cls.get_cart_document(customer_id)
        if not cart or not cart.get("items"):
            raise NotFoundException("Cart item not found.", code="ITEM_NOT_FOUND")

        items: List[dict] = cart.get("items", [])
        original_len = len(items)
        items = [it for it in items if it.get("itemId") != item_id]

        if len(items) == original_len:
            raise NotFoundException("Cart item not found in customer cart.", code="ITEM_NOT_FOUND")

        now = datetime.now(timezone.utc)
        await db.carts.update_one(
            {"_id": cart["_id"]},
            {"$set": {"items": items, "updatedAt": now}},
        )

        cart["items"] = items
        cart["updatedAt"] = now
        return await cls.get_enriched_cart(cart)

    @classmethod
    async def clear_cart(cls, customer_id: str) -> CartResponseData:
        """Clear all items from the customer's cart."""
        db = get_db()
        cart = await cls.get_cart_document(customer_id)
        now = datetime.now(timezone.utc)
        if cart:
            await db.carts.update_one(
                {"_id": cart["_id"]},
                {"$set": {"items": [], "updatedAt": now}},
            )
            cart["items"] = []
            cart["updatedAt"] = now
            return await cls.get_enriched_cart(cart)

        return CartResponseData(
            cartId=f"empty_{customer_id}",
            customerId=customer_id,
            items=[],
            subtotalPaise=0,
            subtotal=0.0,
            currency="INR",
            itemCount=0,
            totalQuantity=0,
            warnings=[],
            updatedAt=now,
        )

    @classmethod
    async def validate_cart(cls, customer_id: str) -> CartValidationResponseData:
        """
        Authoritatively revalidate stock, status, and prices for checkout readiness.
        Does not decrement or reserve stock.
        """
        db = get_db()
        cart = await cls.get_cart_document(customer_id)
        if not cart or not cart.get("items"):
            return CartValidationResponseData(
                valid=True,
                items=[],
                subtotalPaise=0,
                subtotal=0.0,
                currency="INR",
                warnings=[],
            )

        items_raw = cart.get("items", [])
        shop_id = cart.get("shopId")
        prod_ids = [cls._to_object_id(it.get("productId")) or it.get("productId") for it in items_raw]
        var_ids = [cls._to_object_id(it.get("variantId")) or it.get("variantId") for it in items_raw]

        products_map: Dict[str, dict] = {}
        async for p in db.products.find({"_id": {"$in": prod_ids}}):
            products_map[str(p["_id"])] = p

        variants_map: Dict[str, dict] = {}
        async for v in db.product_variants.find({"_id": {"$in": var_ids}}):
            variants_map[str(v["_id"])] = v

        inventory_map: Dict[str, dict] = {}
        if shop_id:
            s_obj_id = cls._to_object_id(shop_id)
            shop_query_ids = [shop_id, s_obj_id] if s_obj_id else [shop_id]
            inv_cursor = db.shop_inventory.find({
                "shopId": {"$in": shop_query_ids},
                "variantId": {"$in": var_ids},
            })
            async for inv in inv_cursor:
                inventory_map[str(inv["variantId"])] = inv

        validation_items: List[CartValidationItem] = []
        is_all_valid = True
        total_subtotal_paise = 0
        warnings: List[str] = []

        for it in items_raw:
            item_id = str(it.get("itemId", ""))
            pid = str(it.get("productId", ""))
            vid = str(it.get("variantId", ""))
            qty = int(it.get("quantity", 1))
            prev_price_paise = it.get("priceSnapshotPaise")

            product = products_map.get(pid)
            variant = variants_map.get(vid)
            inv = inventory_map.get(vid)

            p_name = product.get("name", "Product Unavailable") if product else "Product Unavailable"
            v_name = variant.get("variantName", "Variant Unavailable") if variant else "Variant Unavailable"

            cur_price_paise = None
            if inv and inv.get("pricePaise") is not None:
                cur_price_paise = int(inv["pricePaise"])
            elif variant and variant.get("pricePaise") is not None:
                cur_price_paise = int(variant["pricePaise"])
            else:
                cur_price_paise = prev_price_paise or 0

            avail_stock = 0
            if inv:
                avail_stock = max(inv.get("stockQuantity", 0) - inv.get("reservedQuantity", 0), 0)
                is_inv_avail = inv.get("isAvailable", True)
            else:
                is_inv_avail = variant.get("isActive", True) if variant else False
                avail_stock = 10 if is_inv_avail else 0

            status_str = "valid"
            msg = None

            if not product or not product.get("isActive", True):
                status_str = "product_unavailable"
                msg = f"'{p_name}' is discontinued or inactive."
                is_all_valid = False
                warnings.append(msg)
            elif not variant or not variant.get("isActive", True):
                status_str = "variant_unavailable"
                msg = f"'{p_name} ({v_name})' variant is discontinued or inactive."
                is_all_valid = False
                warnings.append(msg)
            elif not is_inv_avail or avail_stock == 0:
                status_str = "out_of_stock"
                msg = f"'{p_name} ({v_name})' is currently out of stock."
                is_all_valid = False
                warnings.append(msg)
            elif avail_stock < qty:
                status_str = "quantity_reduced"
                msg = f"'{p_name} ({v_name})' only has {avail_stock} units available (requested {qty})."
                is_all_valid = False
                warnings.append(msg)
            elif prev_price_paise is not None and prev_price_paise != cur_price_paise:
                status_str = "price_changed"
                old_rs = prev_price_paise / 100.0
                new_rs = cur_price_paise / 100.0
                msg = f"Price for '{p_name} ({v_name})' changed from ₹{old_rs:.2f} to ₹{new_rs:.2f}."
                is_all_valid = False
                warnings.append(msg)

            if status_str in ("valid", "price_changed"):
                total_subtotal_paise += cur_price_paise * qty
            elif status_str == "quantity_reduced":
                total_subtotal_paise += cur_price_paise * avail_stock

            validation_items.append(
                CartValidationItem(
                    itemId=item_id,
                    productId=pid,
                    variantId=vid,
                    productName=p_name,
                    variantName=v_name,
                    status=status_str,
                    previousPricePaise=prev_price_paise,
                    currentPricePaise=cur_price_paise,
                    previousPrice=round(prev_price_paise / 100.0, 2) if prev_price_paise is not None else None,
                    currentPrice=round(cur_price_paise / 100.0, 2) if cur_price_paise is not None else None,
                    requestedQuantity=qty,
                    availableQuantity=avail_stock,
                    message=msg,
                )
            )

        return CartValidationResponseData(
            valid=is_all_valid,
            items=validation_items,
            subtotalPaise=total_subtotal_paise,
            subtotal=round(total_subtotal_paise / 100.0, 2),
            currency="INR",
            warnings=warnings,
        )

    @classmethod
    async def create_guest_cart(
        cls,
        items: Optional[List[dict]] = None,
        shop_id: Optional[str] = None,
    ) -> dict:
        """Create a new opaque guest cart for an unauthenticated visitor."""
        db = get_db()
        guest_cart_id = f"guest_{secrets.token_urlsafe(16)}"
        resolved_shop_id, _ = await cls.resolve_shop(shop_id=shop_id)
        now = datetime.now(timezone.utc)

        cart_items = []
        if items:
            for it in items:
                cart_items.append({
                    "itemId": str(uuid.uuid4()),
                    "productId": str(it.get("productId")),
                    "variantId": str(it.get("variantId")),
                    "quantity": int(it.get("quantity", 1)),
                    "priceSnapshotPaise": it.get("priceSnapshotPaise", 0),
                    "createdAt": now,
                    "updatedAt": now,
                })

        guest_cart = {
            "_id": ObjectId(),
            "customerId": None,
            "guestCartId": guest_cart_id,
            "shopId": resolved_shop_id,
            "status": "active",
            "items": cart_items,
            "createdAt": now,
            "updatedAt": now,
        }
        await db.carts.insert_one(guest_cart)
        return guest_cart

    @classmethod
    async def merge_guest_cart(
        cls,
        customer_id: str,
        guest_cart_id: str,
    ) -> GuestCartMergeResponseData:
        """
        Merge items from an active guest cart into the authenticated customer's cart.
        Invalidates the guest cart upon completion to prevent replay.
        """
        db = get_db()
        # Find guest cart
        guest_cart = await db.carts.find_one({"guestCartId": guest_cart_id})
        if not guest_cart:
            raise NotFoundException("Guest cart not found.", code="GUEST_CART_NOT_FOUND")

        if guest_cart.get("status") == "merged":
            raise BadRequestException("Guest cart has already been merged.", code="GUEST_CART_ALREADY_MERGED")

        if guest_cart.get("status") != "active":
            raise BadRequestException("Guest cart is inactive or expired.", code="GUEST_CART_INACTIVE")

        # Security check: guest cart MUST NOT have a customerId
        if guest_cart.get("customerId"):
            raise ForbiddenException("Cannot merge an authenticated customer cart as a guest cart.", code="FORBIDDEN_CART_MERGE")

        customer_cart = await cls.get_or_create_customer_cart(customer_id)
        cust_items: List[dict] = customer_cart.get("items", [])
        guest_items: List[dict] = guest_cart.get("items", [])
        now = datetime.now(timezone.utc)

        merged_count = 0
        warnings: List[str] = []

        # Map existing items by variantId
        cust_variant_map: Dict[str, dict] = {str(it.get("variantId")): it for it in cust_items}

        for g_it in guest_items:
            vid = str(g_it.get("variantId"))
            pid = str(g_it.get("productId"))
            g_qty = int(g_it.get("quantity", 1))

            # Verify product & variant are active
            v_obj_id = cls._to_object_id(vid)
            p_obj_id = cls._to_object_id(pid)
            variant = await db.product_variants.find_one({"$or": [{"_id": v_obj_id}, {"_id": vid}] if v_obj_id else {"_id": vid}})
            product = await db.products.find_one({"$or": [{"_id": p_obj_id}, {"_id": pid}] if p_obj_id else {"_id": pid}})

            if not product or not product.get("isActive", True) or not variant or not variant.get("isActive", True):
                warnings.append(f"Guest item (variant: {vid}) is discontinued or inactive and was not merged.")
                continue

            # Check stock
            avail_stock = 999
            price_paise = variant.get("pricePaise", 0)
            shop_id = customer_cart.get("shopId") or guest_cart.get("shopId")
            if shop_id:
                s_obj_id = cls._to_object_id(shop_id)
                shop_query_ids = [shop_id, s_obj_id] if s_obj_id else [shop_id]
                inv = await db.shop_inventory.find_one({
                    "shopId": {"$in": shop_query_ids},
                    "variantId": {"$in": [vid, v_obj_id] if v_obj_id else [vid]},
                })
                if inv:
                    avail_stock = max(inv.get("stockQuantity", 0) - inv.get("reservedQuantity", 0), 0)
                    price_paise = inv.get("pricePaise", price_paise)
                    if not inv.get("isAvailable", True) or avail_stock <= 0:
                        warnings.append(f"Guest item '{product.get('name')}' is out of stock and was not merged.")
                        continue

            if vid in cust_variant_map:
                existing_item = cust_variant_map[vid]
                combined_qty = existing_item.get("quantity", 0) + g_qty
                final_qty = min(combined_qty, cls.MAX_QUANTITY_PER_ITEM, avail_stock)
                if final_qty < combined_qty:
                    warnings.append(
                        f"Quantity for '{product.get('name')}' was capped at {final_qty} due to limit/stock."
                    )
                existing_item["quantity"] = final_qty
                existing_item["priceSnapshotPaise"] = price_paise
                existing_item["updatedAt"] = now
                merged_count += 1
            else:
                final_qty = min(g_qty, cls.MAX_QUANTITY_PER_ITEM, avail_stock)
                if final_qty < g_qty:
                    warnings.append(
                        f"Quantity for '{product.get('name')}' was capped at {final_qty} due to limit/stock."
                    )
                new_item = {
                    "itemId": str(uuid.uuid4()),
                    "productId": str(product["_id"]),
                    "variantId": str(variant["_id"]),
                    "quantity": final_qty,
                    "priceSnapshotPaise": price_paise,
                    "createdAt": now,
                    "updatedAt": now,
                }
                cust_items.append(new_item)
                cust_variant_map[vid] = new_item
                merged_count += 1

        # Atomically invalidate guest cart
        await db.carts.update_one(
            {"_id": guest_cart["_id"]},
            {
                "$set": {
                    "status": "merged",
                    "mergedAt": now,
                    "mergedIntoCustomerId": customer_id,
                    "updatedAt": now,
                }
            },
        )

        # Update customer cart
        await db.carts.update_one(
            {"_id": customer_cart["_id"]},
            {"$set": {"items": cust_items, "updatedAt": now}},
        )

        customer_cart["items"] = cust_items
        customer_cart["updatedAt"] = now
        enriched_cart = await cls.get_enriched_cart(customer_cart)

        return GuestCartMergeResponseData(
            merged=True,
            itemsMergedCount=merged_count,
            cart=enriched_cart,
            warnings=warnings,
        )
