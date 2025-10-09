from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
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

@router.get("/test")
def test_endpoint():
    return {"message": "Test endpoint reached successfully!"}

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
    
    generated_sections = content_agent.generate_proposal_draft(db_proposal)
    
    for section in db_proposal.sections:
        crud.delete_section(db=db, section_id=section.id)

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
def get_design_suggestions(proposal_id: int, db: Session = Depends(get_db)):
    """Get a list of design prompt suggestions from the AI design agent, based on the proposal content."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return design_agent.get_design_suggestions(db_proposal)

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
        # Convert markdown content to HTML
        html_from_markdown = markdown2.markdown(section.contentHtml or "")
        
        # Append images to the section's HTML
        images_html = ""
        if section.images:
            images_html += '<div class="mt-4 grid grid-cols-2 gap-3">';
            for image in section.images:
                placement_class = get_placement_class(section.image_placement)
                images_html += f'<div class="{placement_class}"><img src="{image.url}" alt="Proposal Image" style="max-width: 100%; height: auto; margin-top: 1rem; border-radius: 8px;" /></div>'
            images_html += '</div>'

        # Append mermaid chart to the section's HTML
        mermaid_html = ""
        if section.mermaid_chart:
            mermaid_html = f'<div class="mermaid">{section.mermaid_chart}</div>'
        
        # Get layout class
        layout_class = ""
        if section.layout == 'two-column':
            layout_class = "two-column"

        # Combine title, converted content, and images for the section
        body_content += f"""
            <div class="proposal-section {layout_class}">
                <h2>{section.title}</h2>
                <div class="content-wrapper">
                    {html_from_markdown}
                    {images_html}
                    {mermaid_html}
                </div>
            </div>
        """

    # Construct the full HTML document
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Proposal Preview: {db_proposal.clientName}</title>
        <style>
            .grid {{ display: grid; }}
            .grid-cols-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .gap-3 {{ gap: 0.75rem; }}
            .col-span-full {{ grid-column: 1 / -1; }}
            .col-span-1 {{ grid-column: span 1 / span 1; }}
            .col-start-2 {{ grid-column-start: 2; }}
            .mt-4 {{ margin-top: 1rem; }}
            .two-column .content-wrapper {{ column-count: 2; column-gap: 2rem; }}
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
    return HTMLResponse(content=html_content)

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

    section_update = schemas.SectionUpdate(mermaid_chart=chart_code)
    updated_section = crud.update_section(db=db, section_id=section_id, section=section_update)
    
    return updated_section
