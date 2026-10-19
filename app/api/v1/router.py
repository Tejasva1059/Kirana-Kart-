from fastapi import APIRouter
from app.api.v1.endpoints import auth, customers

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router)
api_v1_router.include_router(customers.router)
