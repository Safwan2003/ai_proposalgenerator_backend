
from fastapi import APIRouter
from .endpoints import proposals, images, sections

api_router = APIRouter()
api_router.include_router(proposals.router, prefix="/proposals", tags=["proposals"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(sections.router, prefix="/sections", tags=["sections"])
