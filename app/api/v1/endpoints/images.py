from fastapi import APIRouter
from typing import List, Dict, Optional
from app.agents.content_agent import content_agent

router = APIRouter()

@router.get("/search", response_model=List[Dict])
def search_images(q: str, tags: Optional[str] = None):
    """Search for relevant public images."""
    return content_agent.search_images(q, tags)