from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.database import get_db
from app.agents.diagram_agent import DiagramAgent

router = APIRouter()

@router.post("/generate_chart", response_model=schemas.Section)
async def generate_chart_for_section_endpoint(
    request: schemas.GenerateChartForSectionRequest,
    db: AsyncSession = Depends(get_db),
):
    db_section = await crud.get_section(db, section_id=request.section_id)
    if not db_section:
        raise HTTPException(status_code=404, detail="Section not found")

    from groq import Groq
    import os
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    diagram_agent = DiagramAgent(client=client)
    mermaid_code = diagram_agent.generate_chart(request.chart_type, request.description)

    update_data = schemas.SectionUpdate(mermaid_chart=mermaid_code, chart_type=request.chart_type)
    updated_section = await crud.update_section(db, section_id=request.section_id, section=update_data)
    return updated_section
