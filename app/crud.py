from sqlalchemy.orm import Session, joinedload
from . import models, schemas
from typing import List

def get_proposal(db: Session, proposal_id: int):
    return db.query(models.Proposal).options(joinedload(models.Proposal.sections).joinedload(models.Section.images)).filter(models.Proposal.id == proposal_id).first()

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

def create_section(db: Session, proposal_id: int, section: schemas.SectionCreate):
    section_data = section.dict()
    image_urls = section_data.pop("images", [])
    mermaid_chart = section_data.pop("mermaid_chart", None)
    
    db_section = models.Section(**section_data, proposal_id=proposal_id)
    
    if mermaid_chart:
        db_section.mermaid_chart = mermaid_chart

    for url in image_urls:
        db_section.images.append(models.Image(url=url))
        
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    return db_section

def update_section(db: Session, section_id: int, section: schemas.SectionUpdate):
    db_section = get_section(db, section_id)
    if db_section:
        # Create a new version with the old content
        version = models.SectionVersion(
            contentHtml=db_section.contentHtml,
            section_id=db_section.id
        )
        db.add(version)
        
        update_data = section.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_section, key, value)
        
        db.commit()
        db.refresh(db_section)
    return db_section

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

def add_image_to_section(db: Session, section_id: int, image_url: str):
    db_section = get_section(db, section_id)
    if db_section:
        db_image = models.Image(url=image_url, section_id=section_id)
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        return db_image
    return None

def remove_image_from_section(db: Session, section_id: int, image_url: str):
    db_section = get_section(db, section_id)
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