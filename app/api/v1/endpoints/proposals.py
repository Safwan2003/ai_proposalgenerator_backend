from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Any

from app import crud, schemas
from app.database import get_db
from app.agents.proposal_manager_agent import proposal_manager_agent

router = APIRouter()

@router.post("/", response_model=schemas.Proposal, summary="Create a new proposal", description="Creates a new proposal with the given data.")
async def create_proposal(
    proposal: schemas.ProposalCreate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Create a new proposal.
    """
    return await crud.create_proposal(db=db, proposal=proposal)

@router.post("/{proposal_id}/generate", response_model=schemas.Proposal, summary="Generate a proposal draft", description="Generates a proposal draft with AI-generated content.")
async def generate_proposal_draft(
    proposal_id: int,
    request: schemas.GenerateProposalDraftRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Generate a proposal draft.
    """
    proposal = await crud.get_proposal(db, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # The proposal from crud.get_proposal is a dict, so we need to convert it to a Pydantic model
    proposal_model = schemas.Proposal(**proposal)

    generated_data = await proposal_manager_agent.generate_proposal_draft(proposal_model, db, sections=request.sections)

    # Update the proposal with the generated sections
    for section_data in generated_data.get("sections", []):
        # Ensure contentHtml is not None
        if section_data.get("contentHtml") is None:
            section_data["contentHtml"] = ""
        section_create = schemas.SectionCreate(**section_data)
        await crud.create_section(db, proposal_id, section_create, section_data.get("order", 0))

    return await crud.get_proposal(db, proposal_id)

@router.get("/{proposal_id}", response_model=schemas.Proposal, summary="Get a single proposal", description="Returns a single proposal by its ID, including all of its sections and their content.")
async def get_proposal(
    proposal_id: int,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Get a single proposal by its ID.
    """
    db_proposal = await crud.get_proposal(db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return db_proposal

@router.patch("/{proposal_id}", response_model=schemas.Proposal, summary="Update a proposal", description="Updates the main details of a proposal, such as the client name, total amount, etc.")
async def update_proposal(
    proposal_id: int,
    proposal: schemas.ProposalUpdate,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Update a proposal.
    """
    db_proposal = await crud.update_proposal(db, proposal_id=proposal_id, proposal=proposal)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return db_proposal
