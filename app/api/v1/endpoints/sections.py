from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.get("/{section_id}/versions", response_model=List[schemas.SectionVersion])
def get_section_versions(section_id: int, db: Session = Depends(get_db)):
    """Get the version history for a section."""
    versions = crud.get_section_versions(db=db, section_id=section_id)
    return versions

@router.post("/{section_id}/revert/{version_id}", response_model=schemas.Section)
def revert_section(section_id: int, version_id: int, db: Session = Depends(get_db)):
    """Revert a section to a previous version."""
    reverted_section = crud.revert_section(db=db, section_id=section_id, version_id=version_id)
    if reverted_section is None:
        raise HTTPException(status_code=404, detail="Section or Version not found")
    return reverted_section

@router.post("/{section_id}/images", response_model=schemas.Image)
def add_image_to_section(section_id: int, image: schemas.ImageCreate, db: Session = Depends(get_db)):
    """Add an image to a section."""
    db_image = crud.add_image_to_section(db=db, section_id=section_id, image_url=image.url)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return db_image
