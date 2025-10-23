from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
import html as html_lib
import re
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse
import markdown2
from app import crud, schemas
import json
import os
from datetime import datetime
from app.agents.content_agent import content_agent
from app.database import get_db
from app.agents.autogen_workflow import run_master_workflow
from app.agents.export_agent import export_agent

router = APIRouter()


from pydantic import BaseModel
from typing import Any, Dict

class AiTaskRequest(BaseModel):
    task_name: str
    context: Dict[str, Any]



@router.post("/{proposal_id}/ai-task")
def perform_ai_task(proposal_id: int, request: AiTaskRequest, db: Session = Depends(get_db)):
    """Run a generic AI task using the master workflow."""
    # Fetch proposal or section if needed by the context


    if request.task_name in ["enhance_section", "suggest_chart"]:
        section = crud.get_section(db=db, section_id=request.context.get("section_id"))
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")
        request.context["content"] = section.contentHtml

    # Run the workflow
    result = run_master_workflow(tool_name=request.task_name, tool_args=request.context)

    if result is None:
        raise HTTPException(status_code=500, detail=f"AI task '{request.task_name}' failed.")

    # Update the database for tasks that modify content
    if request.task_name == "enhance_section" or request.task_name == "generate_content":
        updated_section = crud.update_section(db, section_id=request.context.get("section_id"), section=schemas.SectionUpdate(contentHtml=result))
        return updated_section

    if request.task_name == "live_customize":
        return schemas.DesignSuggestion(prompt=request.context.get("prompt"), css=result)

    if request.task_name == "generate_chart" or request.task_name == "fix_chart":
        return {"chartCode": result}

    # For other tasks, return the direct result
    return result


@router.post("/{proposal_id}/sections/{section_id}/enhance")
def enhance_section(proposal_id: int, section_id: int, request: schemas.EnhanceRequest, db: Session = Depends(get_db)):
    """Enhance a section's content using the AI content agent."""
    section = crud.get_section(db=db, section_id=section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    enhanced_content = content_agent.enhance_section(
        content=section.contentHtml,
        action=request.action,
        tone=request.tone
    )

    if enhanced_content is None:
        raise HTTPException(status_code=500, detail="AI enhancement failed.")

    updated_section = crud.update_section_content(db, section_id=section_id, content=enhanced_content)
    return updated_section


@router.post("", response_model=schemas.Proposal)
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


import logging

@router.post("/{proposal_id}/generate", response_model=schemas.Proposal)
def generate_proposal_draft(proposal_id: int, db: Session = Depends(get_db)):
    """Generate a proposal draft using the AutoGen multi-agent workflow."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Convert the SQLAlchemy model to a Pydantic model to use model_dump_json
    pydantic_proposal = schemas.Proposal.from_orm(db_proposal)

    try:
        result = run_master_workflow(
            tool_name="generate_proposal_draft",
            tool_args=pydantic_proposal.model_dump()
        )

        # Accept multiple possible result shapes from the workflow:
        # 1) dict with key 'sections' -> { 'sections': [...] }
        # 2) plain list of sections -> [ {...}, ... ]
        # 3) falsy/None -> treat as generation failure
        generated_sections = None
        if isinstance(result, dict) and "sections" in result and isinstance(result["sections"], list):
            generated_sections = result["sections"]
        elif isinstance(result, list):
            # If the workflow returned a raw list of sections
            generated_sections = result
        else:
            logging.error(f"Proposal generation returned unexpected result: {type(result)} - {result}")

        if not generated_sections:
            # Generation failed or produced nothing; save raw workflow output for debugging
            try:
                os.makedirs(os.path.join(os.getcwd(), 'temp'), exist_ok=True)
                dump_path = os.path.join(os.getcwd(), 'temp', f'cleaned_ai_response_{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.json')
                with open(dump_path, 'w', encoding='utf-8') as f:
                    json.dump({'workflow_result': result}, f, ensure_ascii=False, indent=2, default=str)
                logging.info(f"Saved unexpected workflow result to {dump_path}")
            except Exception as e:
                logging.error(f"Failed to save workflow result for debugging: {e}")

            # Try a direct fallback: call the content agent's prompt-based generator
            try:
                logging.info("Attempting direct fallback: calling content_agent.generate_proposal_draft")
                fallback_sections = content_agent.generate_proposal_draft(pydantic_proposal)
                if isinstance(fallback_sections, list) and fallback_sections:
                    generated_sections = fallback_sections
                    logging.info("Fallback content_agent produced sections; will use these to populate the proposal.")
                else:
                    logging.warning("Fallback content_agent did not produce sections.")
            except Exception as e:
                logging.exception(f"Fallback content generation failed: {e}")

        if not generated_sections:
            logging.warning("AI proposal content generation produced no sections after fallback. Raising HTTPException.")
            raise HTTPException(status_code=500, detail="AI proposal content generation failed to produce any sections.")

        # Start transaction: clear out old sections and create new ones
        for section in list(db_proposal.sections):
            crud.delete_section(db=db, section_id=section.id)

        for i, section_data in enumerate(generated_sections):
            # Convert image_urls (List[str]) to images (List[ImageObject])
            title = section_data.get("title", "").lower()
            if "image_urls" in section_data and section_data["image_urls"] is not None and "development plan" not in title and "payment milestone" not in title and "user journey" not in title and "workflow" not in title:
                section_data["images"] = [schemas.ImageObject(url=url) for url in section_data["image_urls"]]
                del section_data["image_urls"]
            else:
                section_data["images"] = []

            # Ensure tech_logos is always a list
            if "tech_logos" not in section_data or section_data["tech_logos"] is None:
                section_data["tech_logos"] = []

            crud.create_section(db=db, proposal_id=proposal_id, section=schemas.SectionCreate(**section_data), order=i)

        db.commit()

    except Exception as e:
        db.rollback()
        logging.exception("An error occurred during proposal generation")
        raise HTTPException(status_code=500, detail=f"An error occurred during proposal generation: {e}")

    # Get the updated proposal with new sections
    updated_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)



    # Extract tech stack logos from the generated sections
    dynamic_tech_stack_logos = []
    for section_data in generated_sections:
        if section_data.get("title", "").lower().startswith("technology"):
            dynamic_tech_stack_logos = section_data.get("tech_logos", [])
            break
    updated_proposal.tech_stack = dynamic_tech_stack_logos

    # Also add the tech_logos to the section itself
    for section in updated_proposal.sections:
        if section.title.lower().startswith("technology"):
            section.tech_logos = json.dumps([schemas.TechLogo(**logo).model_dump() for logo in dynamic_tech_stack_logos])
        else:
            # Ensure non-technology sections also have tech_logos as an empty JSON array if not set
            if section.tech_logos is None:
                section.tech_logos = "[]"

    return updated_proposal


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

@router.post("/{proposal_id}/sections/{section_id}/images", response_model=schemas.Image)
def add_image_to_section(proposal_id: int, section_id: int, image: schemas.ImageCreate, db: Session = Depends(get_db)):
    """Add an image to a section."""
    db_proposal = crud.get_proposal(db=db, proposal_id=proposal_id)
    if db_proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")

    db_image = crud.add_image_to_section(db=db, proposal_id=proposal_id, section_id=section_id, image_url=image.url)
    if db_image is None:
        raise HTTPException(status_code=404, detail="Section not found in this proposal")
    return db_image

@router.delete("/{proposal_id}/sections/{section_id}/images")
def remove_image_from_section(proposal_id: int, section_id: int, image: schemas.ImageDelete, db: Session = Depends(get_db)):
    """Remove an image from a section."""
    db_image = crud.remove_image_from_section(db=db, proposal_id=proposal_id, section_id=section_id, image_url=image.url)
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

        image_blocks = []
        if section.images:
            for img in section.images:
                placement_class = get_placement_class(img.placement)
                img_tag = f'<img src="{img.url}" alt="{img.alt or section.title}" style="width:100%; height:auto;" />'
                image_blocks.append(f'<div class="image-block {placement_class}">{img_tag}</div>')
        image_html = "".join(image_blocks)

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
        if section.image_placement == 'full-width-top':
            final_section_content = image_html + text_wrapper
        elif section.image_placement == 'full-width-bottom':
            final_section_content = text_wrapper + image_html
        else:
            # For other placements, embed images within the text_wrapper or default
            # This assumes that image_html contains all image blocks, and they will be styled by CSS
            final_section_content = f"""
            <div style="padding: 2rem 3rem;">
                <h2 style="font-size:1.4rem; color:#2d3748; margin-bottom:0.75rem;">{section.title}</h2>
                <div class="content-wrapper" style="font-size:1rem; color:#333; line-height:1.6;">
                    {image_html}
                    {html_from_markdown}
                    {mermaid_html}
                </div>
            </div>
            """

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
        <script>
            mermaid.initialize({{
                startOnLoad:true,
                theme: 'base',
                themeVariables: {{
                    'primaryColor': '#4F46E5',
                    'primaryTextColor': '#FFFFFF',
                    'primaryBorderColor': '#4338CA',
                    'lineColor': '#6D28D9',
                    'secondaryColor': '#F3F4F6',
                    'tertiaryColor': '#E5E7EB'
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content, headers={'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0'})

# --- The old AI endpoints are now removed, leaving only CRUD and other non-AI endpoints. ---