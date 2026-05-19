from fastapi import APIRouter

from app.api.routes import health
from app.api.v1.router import v1_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(v1_router, prefix="/v1")
