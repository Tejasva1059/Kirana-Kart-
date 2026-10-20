from typing import List, Optional, Tuple, Union
from bson import ObjectId
from app.core.exceptions import NotFoundException
from app.db.mongodb import get_db
from app.schemas.category import CategoryItem


class CategoryService:
    @staticmethod
    def _to_object_id(val: Union[str, ObjectId]) -> Optional[ObjectId]:
        if isinstance(val, ObjectId):
            return val
        try:
            return ObjectId(val)
        except Exception:
            return None

    @classmethod
    async def list_categories(
        cls,
        include_subcategories: bool = False,
        featured_only: bool = False,
        service_area_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[CategoryItem], int]:
        db = get_db()
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)

        query: dict = {
            "isActive": True,
            "$or": [{"parentCategoryId": None}, {"parentCategoryId": {"$exists": False}}, {"parentCategoryId": ""}],
        }
        if featured_only:
            query["isFeatured"] = True

        total = await db.categories.count_documents(query)
        cursor = db.categories.find(query).sort([("sortOrder", 1), ("name", 1)]).skip(offset).limit(limit)

        categories: List[CategoryItem] = []
        cat_ids = []
        async for doc in cursor:
            c_id = str(doc["_id"])
            cat_ids.append(doc["_id"])
            cat_ids.append(c_id)
            categories.append(
                CategoryItem(
                    id=c_id,
                    name=doc.get("name", ""),
                    slug=doc.get("slug", ""),
                    description=doc.get("description"),
                    imageUrl=doc.get("imageUrl"),
                    iconUrl=doc.get("iconUrl"),
                    parentCategoryId=None,
                    sortOrder=doc.get("sortOrder", 1),
                    isFeatured=doc.get("isFeatured", False),
                    subcategories=[] if include_subcategories else None,
                )
            )

        if include_subcategories and categories:
            sub_query = {
                "isActive": True,
                "parentCategoryId": {"$in": cat_ids},
            }
            sub_cursor = db.categories.find(sub_query).sort([("sortOrder", 1), ("name", 1)])
            subs_by_parent: dict = {}
            async for s_doc in sub_cursor:
                p_id = str(s_doc.get("parentCategoryId"))
                item = CategoryItem(
                    id=str(s_doc["_id"]),
                    name=s_doc.get("name", ""),
                    slug=s_doc.get("slug", ""),
                    description=s_doc.get("description"),
                    imageUrl=s_doc.get("imageUrl"),
                    iconUrl=s_doc.get("iconUrl"),
                    parentCategoryId=p_id,
                    sortOrder=s_doc.get("sortOrder", 1),
                    isFeatured=s_doc.get("isFeatured", False),
                )
                subs_by_parent.setdefault(p_id, []).append(item)

            for cat in categories:
                cat.subcategories = subs_by_parent.get(cat.id, [])

        return categories, total

    @classmethod
    async def get_category_by_id(cls, category_id: str) -> CategoryItem:
        db = get_db()
        obj_id = cls._to_object_id(category_id)
        query = {"$or": [{"_id": obj_id}, {"_id": category_id}]} if obj_id else {"_id": category_id}
        doc = await db.categories.find_one(query)

        if not doc or not doc.get("isActive", True):
            raise NotFoundException("Category not found or inactive.", code="CATEGORY_NOT_FOUND")

        parent_id = str(doc.get("parentCategoryId")) if doc.get("parentCategoryId") else None
        return CategoryItem(
            id=str(doc["_id"]),
            name=doc.get("name", ""),
            slug=doc.get("slug", ""),
            description=doc.get("description"),
            imageUrl=doc.get("imageUrl"),
            iconUrl=doc.get("iconUrl"),
            parentCategoryId=parent_id,
            sortOrder=doc.get("sortOrder", 1),
            isFeatured=doc.get("isFeatured", False),
        )

    @classmethod
    async def list_subcategories(cls, parent_category_id: str) -> List[CategoryItem]:
        # Validate parent exists and is active
        await cls.get_category_by_id(parent_category_id)

        db = get_db()
        p_obj_id = cls._to_object_id(parent_category_id)
        parent_variants = [p_obj_id, parent_category_id] if p_obj_id else [parent_category_id]

        query = {
            "isActive": True,
            "parentCategoryId": {"$in": parent_variants},
        }
        cursor = db.categories.find(query).sort([("sortOrder", 1), ("name", 1)])
        subcategories: List[CategoryItem] = []
        async for doc in cursor:
            subcategories.append(
                CategoryItem(
                    id=str(doc["_id"]),
                    name=doc.get("name", ""),
                    slug=doc.get("slug", ""),
                    description=doc.get("description"),
                    imageUrl=doc.get("imageUrl"),
                    iconUrl=doc.get("iconUrl"),
                    parentCategoryId=str(doc.get("parentCategoryId")),
                    sortOrder=doc.get("sortOrder", 1),
                    isFeatured=doc.get("isFeatured", False),
                )
            )
        return subcategories
