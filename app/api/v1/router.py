from fastapi import APIRouter
from app.api.v1.endpoints import (
    addresses,
    auth,
    banners,
    categories,
    customers,
    locations,
    products,
    search,
    serviceability,
    shops,
)

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router)
api_v1_router.include_router(customers.router)
api_v1_router.include_router(addresses.router)
api_v1_router.include_router(serviceability.router)
api_v1_router.include_router(locations.router)
api_v1_router.include_router(banners.router)
api_v1_router.include_router(categories.router)
api_v1_router.include_router(products.router)
api_v1_router.include_router(search.router)
api_v1_router.include_router(shops.router)
