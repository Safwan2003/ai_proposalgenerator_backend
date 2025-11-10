from fastapi import APIRouter

from app.api.v1.endpoints import diagrams

router = APIRouter()

router.include_router(diagrams.router, prefix="/diagrams", tags=["diagrams"])
