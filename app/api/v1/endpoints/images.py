
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from typing import List, Dict
from app.agents.content_agent import content_agent
from app.database import get_db

router = APIRouter()

@router.get("/providers", response_model=List[str])
def get_image_providers():
    """Get a list of available image providers."""
    return ["pixabay"]

@router.get("/search", response_model=List[Dict])
def search_images(q: str = Query(..., alias="query"), provider: str = "pixabay"):
    """Search for images based on a query and provider."""
    return content_agent.search_images(q)

@router.get("/tech-logos/search", response_model=List[Dict])
def search_tech_logos(q: str = Query(..., alias="query"), db: Session = Depends(get_db)):
    """Search for tech logos from both custom DB and Simple Icons."""
    return content_agent.search_tech_logos(db=db, query=q)
