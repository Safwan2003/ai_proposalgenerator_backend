from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app import crud, schemas
from app.database import get_db

router = APIRouter()

@router.put("/{section_id}", response_model=schemas.Section)
async def update_section_endpoint(section_id: int, section: schemas.SectionUpdate, db: AsyncSession = Depends(get_db)):
    db_section = await crud.update_section(db, section_id=section_id, section=section)
    if db_section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return db_section

@router.delete("/{section_id}", response_model=schemas.Section)
async def delete_section_endpoint(section_id: int, db: AsyncSession = Depends(get_db)):
    db_section = await crud.delete_section(db, section_id=section_id)
    if db_section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return db_section

@router.post("/reorder", status_code=204)
async def reorder_sections_endpoint(reorder_requests: List[schemas.ReorderSection], db: AsyncSession = Depends(get_db)):
    await crud.reorder_sections(db, reorder_requests=reorder_requests)
    return
