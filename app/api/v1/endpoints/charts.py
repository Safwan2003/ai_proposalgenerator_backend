from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Dict, Optional
from sqlalchemy.orm import Session
from ....database import get_db
from ....crud import get_section, update_section

router = APIRouter()

class ChartGenerateRequest(BaseModel):
    description: str
    chart_type: str
    section_id: Optional[int] = None

class ChartUpdateRequest(BaseModel):
    prompt: str
    current_chart_code: str

class ChartSuggestRequest(BaseModel):
    # No specific fields needed for suggestion, context comes from path
    pass

class ChartResponse(BaseModel):
    mermaid_chart: str

@router.post("/proposals/{proposal_id}/charts", response_model=Dict)
async def generate_chart(
    proposal_id: int,
    request: ChartGenerateRequest,
    db: Session = Depends(get_db)
):
    # Placeholder for AI logic to generate a new chart for the proposal
    # This should ideally create a new section or update an existing one
    print(f"Generating chart for proposal {proposal_id}: {request.description} ({request.chart_type})")
    generated_mermaid_code = f"graph TD\n    A[Generated {request.chart_type}] --> B[for {request.description}]"
    
    # In a real scenario, you would create a new section or update an existing one
    # For now, we just return the chart code
    return {"mermaid_chart": generated_mermaid_code}

@router.post("/proposals/{proposal_id}/sections/{section_id}/update-chart", response_model=Dict)
async def update_chart(
    proposal_id: int,
    section_id: int,
    request: ChartUpdateRequest,
    db: Session = Depends(get_db)
):
    # Placeholder for AI logic to update an existing chart
    print(f"Updating chart for section {section_id} in proposal {proposal_id} with prompt: {request.prompt}")
    updated_mermaid_code = f"graph TD\n    A[Updated Chart] --> B[from {request.current_chart_code}]\n    B --> C[with {request.prompt}]"
    
    # In a real scenario, you would update the section's mermaid_chart field in the DB
    # For now, we just return the updated chart code
    return {"mermaid_chart": updated_mermaid_code}

@router.post("/proposals/{proposal_id}/sections/{section_id}/suggest-chart", response_model=Dict)
async def suggest_chart_type(
    proposal_id: int,
    section_id: int,
    db: Session = Depends(get_db)
):
    # Placeholder for AI logic to suggest a chart type based on section content
    print(f"Suggesting chart type for section {section_id} in proposal {proposal_id}")
    return {"suggestion": "flowchart"} # Example suggestion

@router.post("/proposals/{proposal_id}/sections/{section_id}/generate-chart", response_model=Dict)
async def generate_chart_for_section(
    proposal_id: int,
    section_id: int,
    request: ChartGenerateRequest,
    db: Session = Depends(get_db)
):
    # Placeholder for AI logic to generate a chart for a specific section
    print(f"Generating chart for section {section_id} in proposal {proposal_id}: {request.description} ({request.chart_type})")
    generated_mermaid_code = f"graph TD\n    A[Section Chart] --> B[for {request.description}]"
    
    # In a real scenario, you would update the section's mermaid_chart field in the DB
    # For now, we just return the chart code
    return {"mermaid_chart": generated_mermaid_code}