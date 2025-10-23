
from fastapi import APIRouter
from .endpoints import proposals, images, sections, charts, logos

api_router = APIRouter()
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(sections.router, prefix="/sections", tags=["sections"])
api_router.include_router(charts.router, tags=["charts"])
api_router.include_router(proposals.router, prefix="/proposals", tags=["proposals"])
api_router.include_router(logos.router, prefix="/logos", tags=["logos"])
