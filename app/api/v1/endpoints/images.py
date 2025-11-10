import logging
from fastapi import APIRouter, Query, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Any
from app.agents.content_writer_agent import content_writer_agent
from app.database import get_db
from app import crud, schemas

router = APIRouter()


@router.post("/sections/{section_id}/images", response_model=schemas.Section, summary="Add an image to a section", description="Adds an image to a specific section of a proposal. The image data, including the URL and caption, is provided in the request body.")
async def add_image_to_section(
    section_id: int,
    image: schemas.ImageCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Add an image to a section.
    """
    section = await crud.get_section(db, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    return await crud.add_image_to_section(db=db, section_id=section_id, image=image)

@router.delete("/sections/{section_id}/images", response_model=schemas.Section, summary="Delete an image from a section", description="Removes an image from a section based on the image ID provided in the request body and returns the updated section.")
async def delete_image_from_section(
    section_id: int,
    image: schemas.ImageDelete,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Delete an image from a section and return updated section."""
    section = await crud.get_section(db, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    updated_section = await crud.delete_image_from_section(db=db, section_id=section_id, image_id=image.id)
    if updated_section is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return updated_section


# ------------------- IMAGE SEARCH ENDPOINTS -------------------
@router.get("/providers", response_model=List[str], summary="Get image providers", description="Returns a list of available image providers (e.g., 'pexels', 'pixabay').")
async def get_image_providers():
    """Get a list of available image providers."""
    return ["pexels", "pixabay", "both"]


@router.get("/search", response_model=List[Dict], summary="Search for images", description="Searches for images from a specified provider based on a query string.")
async def search_images(q: str = Query(..., alias="query"), provider: str = "pixabay"):
    """Search for images based on a query and provider."""
    if not q:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return await content_writer_agent.search_images(q, provider=provider)


@router.get("/tech-logos/search", response_model=List[Dict], summary="Search for tech logos", description="Searches for technology logos from a database of custom logos and Simple Icons.")
async def search_tech_logos(q: str = Query(..., alias="query"), db: AsyncSession = Depends(get_db)):
    """Search for tech logos from both custom DB and Simple Icons."""
    logging.info(f"Searching for tech logos with query: {q}")
    results = await content_writer_agent.search_tech_logos(db=db, query=q)
    logging.info(f"Found {len(results)} tech logos.")
    return results
