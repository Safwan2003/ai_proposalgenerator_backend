from typing import List
from groq import RateLimitError
import logging
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, schemas, models
from app.agents.proposal_manager_agent import proposal_manager_agent
from app.agents.content_writer_agent import content_writer_agent

async def enhance_section_service(section_id: int, enhancement_request: schemas.EnhanceSectionRequest, db: AsyncSession) -> schemas.Section:
    """Service layer for enhancing a section using the ContentWriterAgent."""
    logging.info(f"Starting section enhancement for section_id: {section_id}")
    
    db_section = await crud.get_section(db=db, section_id=section_id)
    if db_section is None:
        logging.error(f"Section with id {section_id} not found in service layer.")
        raise ValueError("Section not found")

    try:
        # Convert the DB model to Pydantic model for the agent
        pydantic_section = schemas.Section.model_validate(db_section)
        
        # If instructions not provided, use enhancement_type as instructions
        instructions = enhancement_request.instructions or enhancement_request.enhancement_type
        
        # Call the content writer agent to enhance the section
        enhanced_content = await content_writer_agent.enhance_section(
            section=pydantic_section,
            instructions=instructions,
            tone=enhancement_request.tone or "professional",
            focus_points=enhancement_request.focus_points
        )
        
        # Update the section with enhanced content
        updated_section = await crud.update_section(
            db=db,
            section_id=section_id,
            section=schemas.SectionUpdate(
                content=enhanced_content["content"],
                title=enhanced_content.get("title", db_section.title)
            )
        )
        
        return schemas.Section.model_validate(updated_section)

    except RateLimitError as e:
        await db.rollback()
        logging.error(f"Groq API rate limit exceeded during section enhancement: {e}")
        raise ValueError("API rate limit exceeded. Please try again later.")
    except Exception as e:
        await db.rollback()
        logging.exception("An error occurred during section enhancement in service layer")
        raise e

async def generate_proposal_draft_service(proposal_id: int, db: AsyncSession) -> List[schemas.Section]:
    """Service layer for generating a proposal draft using the ProposalManagerAgent."""
    logging.info(f"Starting ProposalManagerAgent proposal draft generation for proposal_id: {proposal_id}")
    db_proposal = await crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        logging.error(f"Proposal with id {proposal_id} not found in service layer.")
        raise ValueError("Proposal not found")

    await crud.delete_sections_by_proposal_id(db=db, proposal_id=proposal_id)

    pydantic_proposal = schemas.Proposal.model_validate(db_proposal)

    created_sections = []
    try:
        logging.info(f"Running ProposalManagerAgent.generate_proposal_draft for proposal_id: {proposal_id}")
        result = await proposal_manager_agent.generate_proposal_draft(pydantic_proposal, db)
        generated_sections_data = result["sections"]




        for i, section_data in enumerate(generated_sections_data):
            logging.info(f"Service: Received section data from ProposalManagerAgent: {section_data.get('title')}")
            if section_data:
                # The id from the generator is a temporary one, so we don't pass it to create_section
                section_data.pop('id', None)
                logging.info(f"Section data passed to crud.create_section: {section_data}")
                section_create_schema = schemas.SectionCreate(**section_data)
                created_section = await crud.create_section(db=db, proposal_id=proposal_id, section=section_create_schema, order=i)
                created_sections.append(schemas.Section.model_validate(created_section))

        return created_sections

    except RateLimitError as e:
        await db.rollback()
        logging.error(f"Groq API rate limit exceeded: {e}")
        raise ValueError("API rate limit exceeded. Please try again later.")
    except Exception as e:
        await db.rollback()
        logging.exception("An error occurred during proposal generation in service layer")
        raise e
