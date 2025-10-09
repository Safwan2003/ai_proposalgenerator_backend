
from fastapi import APIRouter, Query
from typing import List, Dict
from app.agents.content_agent import content_agent

router = APIRouter()

@router.get("/providers", response_model=List[str])
def get_image_providers():
    """Get a list of available image providers."""
    return ["pixabay"]

@router.get("/search", response_model=List[Dict])
def search_images(q: str = Query(..., alias="query"), provider: str = "pixabay"):
    """Search for images based on a query and provider."""
    return content_agent.search_images(q, provider)
