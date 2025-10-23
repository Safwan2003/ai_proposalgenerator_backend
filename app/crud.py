import json
from sqlalchemy.orm import Session, selectinload
from . import models, schemas
from typing import List

def get_proposal(db: Session, proposal_id: int):
    return db.query(models.Proposal).options(selectinload(models.Proposal.sections).selectinload(models.Section.images)).filter(models.Proposal.id == proposal_id).first()

def get_proposals(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Proposal).offset(skip).limit(limit).all()

def create_proposal(db: Session, proposal: schemas.ProposalCreate):
    db_proposal = models.Proposal(**proposal.dict())
    db.add(db_proposal)
    db.commit()
    db.refresh(db_proposal)
    return db_proposal

def get_section(db: Session, section_id: int):
    return db.query(models.Section).filter(models.Section.id == section_id).first()

def create_section(db: Session, section: schemas.SectionCreate, proposal_id: int, order: int):
    db_section = models.Section(
        title=section.title,
        contentHtml=section.contentHtml,
        order=order,
        image_placement=section.image_placement,
        mermaid_chart=section.mermaid_chart,
        layout=section.layout,
        proposal_id=proposal_id
    )
    if section.tech_logos:
        db_section.tech_logos = json.dumps([logo.model_dump() for logo in section.tech_logos])

    db.add(db_section)
    db.commit()
    db.refresh(db_section)

    for img in section.images:
        db_image = models.Image(url=img.url, alt=img.alt, placement=img.placement, section_id=db_section.id)
        db.add(db_image)
    db.commit()
    db.refresh(db_section)
    return db_section

def update_section(db: Session, section_id: int, section: schemas.SectionUpdate):
    db_section = db.query(models.Section).filter(models.Section.id == section_id).first()
    if not db_section:
        return None

    update_data = section.model_dump(exclude_unset=True)
    if "tech_logos" in update_data and update_data["tech_logos"] is not None:
        db_section.tech_logos = json.dumps([logo.model_dump() for logo in update_data["tech_logos"]])
        del update_data["tech_logos"]
    elif "tech_logos" in update_data and update_data["tech_logos"] is None:
        db_section.tech_logos = "[]" # Store as empty JSON array string
        del update_data["tech_logos"]

    for key, value in update_data.items():
        setattr(db_section, key, value)

    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    return db_section

def update_section_content(db: Session, section_id: int, content: str):
    db_section = db.query(models.Section).filter(models.Section.id == section_id).first()
    if not db_section:
        return None

    db.refresh(db_section)

    # Re-fetch the section with all its relationships loaded
    return db.query(models.Section).options(selectinload(models.Section.images)).filter(models.Section.id == section_id).first()

def delete_section(db: Session, section_id: int):
    db_section = get_section(db, section_id)
    if db_section:
        db.delete(db_section)
        db.commit()
    return db_section

def reorder_sections(db: Session, reorder_requests: List[schemas.ReorderSection]):
    for reorder_request in reorder_requests:
        db_section = get_section(db, reorder_request.sectionId)
        if db_section:
            db_section.order = reorder_request.newOrder
    db.commit()
    return True

def get_section_versions(db: Session, section_id: int):
    return db.query(models.SectionVersion).filter(models.SectionVersion.section_id == section_id).all()

def revert_section(db: Session, section_id: int, version_id: int):
    version = db.query(models.SectionVersion).filter(models.SectionVersion.id == version_id).first()
    if version and version.section_id == section_id:
        db_section = get_section(db, section_id)
        if db_section:
            # Create a new version with the current content before reverting
            current_version = models.SectionVersion(
                contentHtml=db_section.contentHtml,
                section_id=db_section.id
            )
            db.add(current_version)

            db_section.contentHtml = version.contentHtml
            db.commit()
            db.refresh(db_section)
            return db_section
    return None

def add_image_to_section(db: Session, proposal_id: int, section_id: int, image_url: str):
    db_section = db.query(models.Section).filter(models.Section.id == section_id, models.Section.proposal_id == proposal_id).first()
    if db_section:
        db_image = models.Image(url=image_url, section_id=section_id)
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        return db_image
    return None

def remove_image_from_section(db: Session, proposal_id: int, section_id: int, image_url: str):
    db_section = db.query(models.Section).filter(models.Section.id == section_id, models.Section.proposal_id == proposal_id).first()
    if db_section:
        db_image = db.query(models.Image).filter(models.Image.section_id == section_id, models.Image.url == image_url).first()
        if db_image:
            db.delete(db_image)
            db.commit()
            return db_image
    return None

def update_image_placement(db: Session, section_id: int, image_placement: str):
    db_section = get_section(db, section_id)
    if db_section:
        db_section.image_placement = image_placement
        db.commit()
        db.refresh(db_section)
        return db_section
    return None

def update_proposal_css(db: Session, proposal_id: int, css: str):
    db_proposal = get_proposal(db, proposal_id)
    if db_proposal:
        db_proposal.custom_css = css
        db.commit()
        db.refresh(db_proposal)
        return db_proposal
    return None

def get_custom_logo(db: Session, logo_id: int):
    return db.query(models.CustomLogo).filter(models.CustomLogo.id == logo_id).first()

def get_custom_logos(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.CustomLogo).offset(skip).limit(limit).all()

def create_custom_logo(db: Session, logo: schemas.CustomLogoCreate):
    db_logo = models.CustomLogo(**logo.model_dump())
    db.add(db_logo)
    db.commit()
    db.refresh(db_logo)
    return db_logo

def delete_custom_logo(db: Session, logo_id: int):
    db_logo = get_custom_logo(db, logo_id)
    if db_logo:
        db.delete(db_logo)
        db.commit()
    return db_logo