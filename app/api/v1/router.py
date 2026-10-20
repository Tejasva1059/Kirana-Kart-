from fastapi import APIRouter
from app.api.v1.endpoints import addresses, auth, customers, locations, serviceability

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router)
api_v1_router.include_router(customers.router)
api_v1_router.include_router(addresses.router)
api_v1_router.include_router(serviceability.router)
api_v1_router.include_router(locations.router)
