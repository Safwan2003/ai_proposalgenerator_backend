
from fastapi import APIRouter
from .endpoints import proposals, images, sections, ai_content, diagrams, user_images

api_router = APIRouter()
api_router.include_router(proposals.router, prefix="/proposals", tags=["proposals"])
api_router.include_router(sections.router, prefix="/sections", tags=["sections"])
api_router.include_router(ai_content.router, prefix="/ai", tags=["ai-content"])
api_router.include_router(diagrams.router, prefix="/diagrams", tags=["diagrams"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(user_images.router, prefix="/user-images", tags=["user-images"])
