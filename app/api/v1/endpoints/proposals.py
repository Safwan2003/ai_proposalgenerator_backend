from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
import html as html_lib
import re
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse
import markdown2
from app import crud, schemas
from app.database import get_db
from app.agents.content_agent import content_agent
from app.agents.design_agent import design_agent
from app.agents.automation_agent import automation_agent
from app.agents.export_agent import export_agent
from app.agents.diagram_agent import diagram_agent

router = APIRouter()

@router.post("/", response_model=schemas.Proposal)
def create_proposal(proposal: schemas.ProposalCreate, db: Session = Depends(get_db)):
    """Create a new proposal."""
    return crud.create_proposal(db=db, proposal=proposal)

@router.get("/{proposal_id}", response_model=schemas.Proposal)
def get_proposal(proposal_id: int, db: Session = Depends(get_db)):
    """Get a proposal by ID."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return db_proposal

@router.post("/{proposal_id}/generate", response_model=schemas.Proposal)
def generate_proposal_draft(proposal_id: int, db: Session = Depends(get_db)):
    """Generate a proposal draft using AI."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    # 1. Generate proposal content and design hints from the Content Agent
    generated_sections = content_agent.generate_proposal_draft(db_proposal)

    # Create a temporary, in-memory proposal object for the Design Agent
    class TempProposal:
        def __init__(self, proposal, sections):
            self.clientName = proposal.clientName
            self.companyName = proposal.companyName
            self.rfpText = proposal.rfpText
            self.sections = sections

    temp_proposal = TempProposal(db_proposal, generated_sections)

    # 2. Generate context-aware design from the Design Agent using hints
    collaborative_css = design_agent.generate_collaborative_design(temp_proposal)
    crud.update_proposal_css(db=db, proposal_id=proposal_id, css=collaborative_css)

    # 3. Clear out old sections from the database
    for section in crud.get_proposal(db=db, proposal_id=proposal_id).sections:
        crud.delete_section(db=db, section_id=section.id)

    # 4. Create the new sections in the database
    for section_data in generated_sections:
        crud.create_section(db=db, proposal_id=proposal_id, section=schemas.SectionCreate(**section_data))

    return crud.get_proposal(db=db, proposal_id=proposal_id)

@router.post("/{proposal_id}/sections", response_model=schemas.Proposal)
def add_new_section(proposal_id: int, section: schemas.SectionCreate, db: Session = Depends(get_db)):
    """Add a new section to a proposal."""
    crud.create_section(db=db, proposal_id=proposal_id, section=section)
    return crud.get_proposal(db=db, proposal_id=proposal_id)

@router.patch("/{proposal_id}/sections/{section_id}", response_model=schemas.Proposal)
def update_section(proposal_id: int, section_id: int, section_update: schemas.SectionUpdate, db: Session = Depends(get_db)):
    """Update a section's content."""
    updated_section = crud.update_section(db=db, section_id=section_id, section=section_update)
    if updated_section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return crud.get_proposal(db=db, proposal_id=proposal_id)

@router.patch("/{proposal_id}/reorder")
def reorder_sections(reorder_requests: List[schemas.ReorderSection], db: Session = Depends(get_db)):
    """Reorder sections in a proposal."""
    crud.reorder_sections(db=db, reorder_requests=reorder_requests)
    return {"message": "Sections reordered successfully"}

@router.delete("/{proposal_id}/sections/{section_id}")
def delete_section(section_id: int, db: Session = Depends(get_db)):
    """Delete a section from a proposal."""
    crud.delete_section(db=db, section_id=section_id)
    return {"message": "Section deleted successfully"}

@router.post("/{proposal_id}/sections/{section_id}/ai-enhance", response_model=schemas.Section)
def ai_enhance_section(section_id: int, action: str = "rewrite", tone: str = "professional", db: Session = Depends(get_db)):
    """Regenerate/enhance a section using AI."""
    section = crud.get_section(db=db, section_id=section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    
    enhanced_content = content_agent.enhance_section(section.contentHtml, action, tone)
    section_update = schemas.SectionUpdate(contentHtml=enhanced_content)
    updated_section = crud.update_section(db=db, section_id=section_id, section=section_update)
    return updated_section

@router.post("/{proposal_id}/sections/{section_id}/images", response_model=schemas.Image)
def add_image_to_section(section_id: int, image: schemas.ImageCreate, db: Session = Depends(get_db)):
    """Add an image to a section."""
    db_image = crud.add_image_to_section(db=db, section_id=section_id, image_url=image.url)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return db_image

@router.delete("/{proposal_id}/sections/{section_id}/images")
def remove_image_from_section(section_id: int, image: schemas.ImageDelete, db: Session = Depends(get_db)):
    """Remove an image from a section."""
    db_image = crud.remove_image_from_section(db=db, section_id=section_id, image_url=image.url)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Image not found in section")
    return {"message": "Image removed successfully"}

@router.patch("/{proposal_id}/sections/{section_id}/image-placement", response_model=schemas.Section)
def update_image_placement(section_id: int, image_placement: str = Body(..., embed=True), db: Session = Depends(get_db)):
    """Update the image placement for a section."""
    db_section = crud.update_image_placement(db=db, section_id=section_id, image_placement=image_placement)
    if db_section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return db_section


@router.post("/proposals/{proposal_id}/sections/generate-content", response_model=schemas.Section)
def generate_content_for_section(proposal_id: int, request: schemas.GenerateContentRequest, db: Session = Depends(get_db)):
    """Generate content for a section based on keywords using AI."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    section = crud.get_section(db=db, section_id=request.section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    generated_content = content_agent.generate_content_from_keywords(request.keywords)
    section_update = schemas.SectionUpdate(contentHtml=generated_content)
    updated_section = crud.update_section(db=db, section_id=request.section_id, section=section_update)
    return updated_section

@router.get("/{proposal_id}/suggestions")
def get_suggestions(context: str):
    """Get smart suggestions for a proposal section."""
    return automation_agent.get_smart_suggestions(context)

@router.post("/{proposal_id}/sections/{section_id}/suggest-chart", response_model=str)
def suggest_chart_for_section(section_id: int, db: Session = Depends(get_db)):
    """Suggest a chart type for a section."""
    section = crud.get_section(db=db, section_id=section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")
    return diagram_agent.suggest_chart_type(section.contentHtml)

@router.post("/{proposal_id}/expand-bullets")
def expand_bullets(bullet_points: List[str]):
    """Expand bullet points into a paragraph."""
    return {"expanded_text": automation_agent.expand_bullet_points(bullet_points)}

@router.get("/{proposal_id}/design-suggestions", response_model=List[schemas.DesignSuggestion])
async def get_design_suggestions(proposal_id: int, keywords: str = "", db: Session = Depends(get_db)):
    """Get a list of design prompt suggestions from the AI design agent, based on the proposal content."""
    import logging
    logger = logging.getLogger(__name__)
    
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        # Get suggestions from design agent
        suggestions = design_agent.get_design_suggestions(db_proposal, keywords)
        if not suggestions:
            logger.error("No suggestions returned from design agent")
            raise HTTPException(
                status_code=500,
                detail="No design suggestions were generated. Please try again."
            )
        
        # Process and validate each suggestion
        valid_suggestions = []
        for i, suggestion in enumerate(suggestions):
            try:
                if not isinstance(suggestion, dict):
                    logger.error(f"Suggestion {i} is not a dict: {type(suggestion)}")
                    continue
                    
                if "prompt" not in suggestion or "css" not in suggestion:
                    logger.error(f"Suggestion {i} missing required fields: {suggestion.keys()}")
                    continue
                    
                if not isinstance(suggestion["prompt"], str) or not isinstance(suggestion["css"], str):
                    logger.error(f"Suggestion {i} has invalid types: prompt={type(suggestion['prompt'])}, css={type(suggestion['css'])}")
                    continue
                
                # Clean any format specifiers
                prompt = suggestion["prompt"].replace("%", "%%")
                css = suggestion["css"].replace("%", "%%")
                
                # Create validated suggestion
                valid_suggestions.append(
                    schemas.DesignSuggestion(
                        prompt=prompt,
                        css=css
                    )
                )
            except Exception as e:
                logger.error(f"Error processing suggestion {i}: {str(e)}")
                continue
        
        if not valid_suggestions:
            logger.error("No valid suggestions after processing")
            # Return default design if no valid suggestions
            default = design_agent.get_default_design()[0]
            return [schemas.DesignSuggestion(
                prompt=default["prompt"],
                css=default["css"]
            )]
            
        return valid_suggestions
        
    except ValueError as e:
        logger.error(f"ValueError in design suggestions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating design suggestions: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in design suggestions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}"
        )

@router.post("/{proposal_id}/apply-design", response_model=schemas.Proposal)
def apply_design(proposal_id: int, css: str = Body(..., embed=True), db: Session = Depends(get_db)):
    """Apply a custom design to a proposal."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    db_proposal.custom_css = css
    db.commit()
    db.refresh(db_proposal)
    
    return db_proposal

@router.get("/{proposal_id}/preview", response_class=HTMLResponse)
def preview_proposal(proposal_id: int, db: Session = Depends(get_db)):
    """Returns a full HTML preview of the proposal with custom styling."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Combine all section HTML, converting from Markdown and adding images
    body_content = ""

    def get_placement_class(placement):
        if placement == 'full-width':
            return 'col-span-full'
        if placement == 'inline-left':
            return 'col-span-1'
        if placement == 'inline-right':
            return 'col-span-1 col-start-2'
        if placement == 'two-column-left':
            return 'col-span-2'
        if placement == 'two-column-right':
            return 'col-span-2 col-start-3'
        if placement == 'three-column':
            return 'col-span-3'
        return 'col-span-1'

    for section in sorted(db_proposal.sections, key=lambda s: s.order if s.order is not None else 999):
        # Prepare content: unescape HTML entities then decide if it's raw HTML or markdown
        raw = section.contentHtml or ""
        raw = html_lib.unescape(raw)

        # Heuristic: if content already contains HTML tags, treat as HTML; otherwise convert from markdown
        if re.search(r"<\/?[a-zA-Z][\s\S]*?>", raw):
            html_from_markdown = raw
        else:
            html_from_markdown = markdown2.markdown(raw)

        # Prepare mermaid HTML if present
        mermaid_html = ""
        if section.mermaid_chart:
            mermaid_html = f'<div class="mermaid">{section.mermaid_chart}</div>'

        is_full_width = section.image_placement in ('full-width-top', 'full-width-bottom')

        image_html = ""
        if is_full_width and section.images:
            # Image will be a direct child of the non-padded section
            image_html = f'<div><img src="{section.images[0].url}" alt="{section.title}" style="width:100%; height:auto;" /></div>'

        # Text content is always wrapped in a div with padding
        text_wrapper = f"""
        <div style="padding: 2rem 3rem;">
            <h2 style="font-size:1.4rem; color:#2d3748; margin-bottom:0.75rem;">{section.title}</h2>
            <div class="content-wrapper" style="font-size:1rem; color:#333; line-height:1.6;">
                {html_from_markdown}
                {mermaid_html}
            </div>
        </div>
        """

        # Assemble the section content based on image placement
        final_section_content = ""
        if is_full_width:
            if section.image_placement == 'full-width-top':
                final_section_content = image_html + text_wrapper
            else:
                final_section_content = text_wrapper + image_html
        else:
            # For sections without full-width images, just use the padded text wrapper
            final_section_content = text_wrapper

        layout_class = ""
        if section.layout == 'two-column':
            layout_class = "two-column"

        # The outer section container has no padding, allowing images to be full-width
        body_content += f'<div class="proposal-section {layout_class}" style="padding:0; overflow: hidden;">{final_section_content}</div>'

    # Construct the full HTML document
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Proposal Preview: {db_proposal.clientName}</title>
        <style>
            body {{ background-color: #f0f0f0; }}
            .grid {{ display: grid; }}
            .grid-cols-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .gap-3 {{ gap: 0.75rem; }}
            .col-span-full {{ grid-column: 1 / -1; }}
            .col-span-1 {{ grid-column: span 1 / span 1; }}
            .col-start-2 {{ grid-column-start: 2; }}
            .mt-4 {{ margin-top: 1rem; }}
            .two-column .content-wrapper {{ column-count: 2; column-gap: 2rem; }}
            .proposal-container {{
                max-width: 1000px;
                margin: 0 auto;
                background-color: white;
            }}
            {db_proposal.custom_css or ""}
        </style>
    </head>
    <body>
        <div class="proposal-container">
            <h1>Proposal for {db_proposal.clientName}</h1>
            {body_content}
        </div>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
        <script>mermaid.initialize({{startOnLoad:true}});</script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'})

@router.post("/{proposal_id}/export")
def export_proposal(proposal_id: int, format: str = "docx", db: Session = Depends(get_db)):
    """Export a proposal to DOCX or PDF."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if format == "docx":
        file_path = export_agent.export_to_docx(db_proposal)
    elif format == "pdf":
        file_path = export_agent.export_to_pdf(db_proposal)
    else:
        raise HTTPException(status_code=400, detail="Invalid export format")

    if not file_path:
        raise HTTPException(status_code=500, detail="Failed to generate export file")

    return {"download_url": file_path}

@router.post("/{proposal_id}/sections/generate-chart", response_model=schemas.Proposal)
def generate_chart_section(proposal_id: int, request: schemas.GenerateChartRequest, db: Session = Depends(get_db)):
    """Generate a new section with a Mermaid chart."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if request.chart_type == 'flowchart':
        chart_code = diagram_agent.generate_flowchart(request.description)
        title = "Flowchart"
    elif request.chart_type == 'gantt':
        chart_code = diagram_agent.generate_gantt_chart(request.description)
        title = "Gantt Chart"
    else:
        raise HTTPException(status_code=400, detail="Invalid chart type")

    if not chart_code:
        raise HTTPException(status_code=422, detail="AI failed to generate valid Mermaid chart code. Please try a different description or chart type.")

    new_section_data = schemas.SectionCreate(
        title=title,
        contentHtml="",
        mermaid_chart=chart_code,
        order=len(db_proposal.sections) + 1
    )
    crud.create_section(db=db, proposal_id=proposal_id, section=new_section_data)

    return crud.get_proposal(db=db, proposal_id=proposal_id)

@router.post("/{proposal_id}/sections/{section_id}/update-chart", response_model=schemas.Section)
def update_chart_section(proposal_id: int, section_id: int, request: schemas.UpdateChartRequest, db: Session = Depends(get_db)):
    """Update a section's Mermaid chart using AI."""
    db_section = crud.get_section(db=db, section_id=section_id)
    if db_section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    updated_chart_code = diagram_agent.update_chart(
        prompt=request.prompt,
        current_chart_code=request.current_chart_code
    )

    if not updated_chart_code:
        raise HTTPException(status_code=500, detail="Failed to update chart")

    section_update = schemas.SectionUpdate(mermaid_chart=updated_chart_code)
    updated_section = crud.update_section(db=db, section_id=section_id, section=section_update)
    return updated_section

@router.post("/{proposal_id}/sections/{section_id}/generate-chart", response_model=schemas.Section)
def generate_chart_for_section(proposal_id: int, section_id: int, request: schemas.GenerateChartForSectionRequest, db: Session = Depends(get_db)):
    """Generate a chart and add it to an existing section."""
    db_section = crud.get_section(db=db, section_id=section_id)
    if db_section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    if request.chart_type == 'flowchart':
        chart_code = diagram_agent.generate_flowchart(request.description)
    elif request.chart_type == 'gantt':
        chart_code = diagram_agent.generate_gantt_chart(request.description)
    else:
        raise HTTPException(status_code=400, detail="Invalid chart type")

    if not chart_code:
        raise HTTPException(status_code=422, detail="AI failed to generate valid Mermaid chart code. Please try a different description or chart type.")

    return updated_section

@router.post("/{proposal_id}/live-customize", response_model=schemas.DesignSuggestion)
async def live_customize_design(proposal_id: int, request: schemas.LiveCustomizeRequest, db: Session = Depends(get_db)):
    """Applies a live customization to the proposal's CSS using AI."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if not db_proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    current_css = db_proposal.custom_css or ""
    
    # Use the existing customize_design method in the agent
    new_css = design_agent.customize_design(
        css=current_css,
        customization_request=request.prompt
    )

    if not new_css or new_css == current_css:
        raise HTTPException(status_code=500, detail="AI could not modify the design. Try a different prompt.")

    # Return the new CSS for live preview
    return schemas.DesignSuggestion(prompt=request.prompt, css=new_css)
