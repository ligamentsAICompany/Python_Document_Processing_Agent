from fastapi import APIRouter

from app.api.v1 import documents, health

v1_router = APIRouter()
v1_router.include_router(health.router)
v1_router.include_router(documents.router)
