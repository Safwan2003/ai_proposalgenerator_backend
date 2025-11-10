from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.database import get_db
from app.services.proposal_service import enhance_section_service

router = APIRouter()

@router.post("/enhance_section", response_model=schemas.Section)
async def enhance_section_endpoint(request: schemas.EnhanceSectionRequest, db: AsyncSession = Depends(get_db)):
    return await enhance_section_service(section_id=request.section_id, enhancement_request=request, db=db)
