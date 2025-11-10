import logging
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from . import models, schemas


# ---------------------------------------------------------------------------
# USER IMAGE CRUD
# ---------------------------------------------------------------------------

async def get_user_images(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.UserImage]:
    """
    Retrieves a list of user images with pagination.
    """
    result = await db.execute(
        select(models.UserImage)
        .order_by(models.UserImage.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_user_image(db: AsyncSession, image: schemas.UserImageCreate) -> models.UserImage:
    """
    Creates a new user image record in the database.
    """
    db_image = models.UserImage(url=image.url)
    db.add(db_image)
    await db.commit()
    await db.refresh(db_image)
    return db_image

async def delete_user_image(db: AsyncSession, image_id: int) -> Optional[models.UserImage]:
    """
    Deletes a user image from the database by its ID.
    """
    result = await db.execute(select(models.UserImage).filter(models.UserImage.id == image_id))
    db_image = result.scalar_one_or_none()
    if db_image:
        await db.delete(db_image)
        await db.commit()
    return db_image


# ---------------------------------------------------------------------------
# IMAGE DELETION (correct version)
# ---------------------------------------------------------------------------

async def delete_image_from_section(db: AsyncSession, section_id: int, image_id: int) -> models.Section:
    section = await get_section(db, section_id)
    if not section:
        return None
    
    if image_id < len(section.image_urls):
        section.image_urls.pop(image_id)
        db.add(section)
        await db.commit()
        await db.refresh(section)
    
    return section


# ---------------------------------------------------------------------------
# PROPOSAL CRUD
# ---------------------------------------------------------------------------

async def get_proposal(db: AsyncSession, proposal_id: int) -> Optional[dict]:
    result = await db.execute(
        select(models.Proposal).options(
            selectinload(models.Proposal.sections)
        ).filter(models.Proposal.id == proposal_id)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        return None

    # Sort sections by order
    sorted_sections = sorted(proposal.sections, key=lambda s: s.order)

    proposal_dict = {
        "id": proposal.id,
        "clientName": proposal.clientName,
        "rfpText": proposal.rfpText,
        "totalAmount": proposal.totalAmount,
        "paymentType": proposal.paymentType,
        "numDeliverables": proposal.numDeliverables,
        "startDate": proposal.startDate,
        "endDate": proposal.endDate,
        "companyName": proposal.companyName,
        "companyLogoUrl": proposal.companyLogoUrl,
        "companyContact": proposal.companyContact,
        "custom_css": proposal.custom_css,
        "sections": [
            {
                "id": section.id,
                "proposal_id": section.proposal_id,
                "title": section.title,
                "contentHtml": section.contentHtml,
                "order": section.order,
                "image_placement": section.image_placement,
                "mermaid_chart": section.mermaid_chart,
                "layout": section.layout,
                "chart_type": section.chart_type,
                "tech_logos": section.tech_logos or [],
                "images": [{"id": i, "url": url, "alt": "", "placement": section.image_placement or "full-width-top"} for i, url in enumerate(section.image_urls or [])]
            }
            for section in sorted_sections
        ]
    }
    return proposal_dict

async def add_image_to_section(db: AsyncSession, section_id: int, image: schemas.ImageCreate) -> models.Section:
    section = await get_section(db, section_id)
    if not section:
        return None
    
    # Initialize image_urls if it's None
    if section.image_urls is None:
        section.image_urls = []
    
    section.image_urls.append(image.url)
    db.add(section)
    await db.commit()
    await db.refresh(section)
    return section


async def get_proposals(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Proposal]:
    result = await db.execute(select(models.Proposal).offset(skip).limit(limit))
    return result.scalars().all()


async def create_proposal(db: AsyncSession, proposal: schemas.ProposalCreate) -> models.Proposal:
    db_proposal = models.Proposal(**proposal.model_dump())
    db.add(db_proposal)
    await db.commit()
    await db.refresh(db_proposal)
    return await get_proposal(db, db_proposal.id)

async def update_proposal(db: AsyncSession, proposal_id: int, proposal: schemas.ProposalUpdate) -> Optional[dict]:
    result = await db.execute(select(models.Proposal).filter(models.Proposal.id == proposal_id))
    db_proposal = result.scalar_one_or_none()
    if not db_proposal:
        return None
    update_data = proposal.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_proposal, key, value)
    db.add(db_proposal)
    await db.commit()
    await db.refresh(db_proposal)
    return await get_proposal(db, db_proposal.id)


# ---------------------------------------------------------------------------
# SECTION CRUD
# ---------------------------------------------------------------------------

async def get_section(db: AsyncSession, section_id: int) -> Optional[models.Section]:
    result = await db.execute(
        select(models.Section)
        .filter(models.Section.id == section_id)
    )
    return result.scalar_one_or_none()


async def create_section(db: AsyncSession, proposal_id: int, section: schemas.SectionCreate, order: Optional[int] = None) -> models.Section:
    # If an order is specified, shift existing sections to make space
    if order is not None:
        # Fetch all sections for the proposal that have an order >= the new order
        sections_to_shift_result = await db.execute(
            select(models.Section)
            .where(models.Section.proposal_id == proposal_id)
            .where(models.Section.order >= order)
        )
        sections_to_shift = sections_to_shift_result.scalars().all()

        # Increment their order by 1
        for s in sections_to_shift:
            s.order += 1
            db.add(s)
        await db.flush() # Flush to ensure order changes are reflected before adding new section

    # If order was not provided, determine it (should be handled by the endpoint now, but as a fallback)
    if order is None:
        existing_sections_result = await db.execute(
            select(models.Section.order)
            .where(models.Section.proposal_id == proposal_id)
            .order_by(models.Section.order.desc())
            .limit(1)
        )
        max_order = existing_sections_result.scalar_one_or_none()
        order = (max_order if max_order is not None else 0) + 1

    section_data = section.model_dump(exclude={"order"})
    # Convert optional images list to image_urls if provided, and drop unsupported field
    images_value = section_data.pop("images", None)
    if images_value and isinstance(images_value, list):
        try:
            section_data["image_urls"] = [
                (img["url"] if isinstance(img, dict) else str(img)) for img in images_value
            ]
        except Exception:
            # Fallback: ignore invalid images payloads
            pass
    db_section = models.Section(**section_data, proposal_id=proposal_id, order=order)
    db.add(db_section)
    await db.commit()
    await db.refresh(db_section)
    return db_section


async def update_section(db: AsyncSession, section_id: int, section: schemas.SectionUpdate) -> Optional[models.Section]:
    db_section = await get_section(db, section_id)
    if not db_section:
        logging.warning(f"Section with ID {section_id} not found for update.")
        return None
    update_data = section.model_dump(exclude_unset=True)
    # If client sent images array of objects, convert to image_urls and drop images
    images_value = update_data.pop("images", None)
    if images_value and isinstance(images_value, list):
        try:
            update_data["image_urls"] = [
                (img.get("url") if isinstance(img, dict) else str(img)) for img in images_value
            ]
        except Exception:
            pass
    for key, value in update_data.items():
        setattr(db_section, key, value)
    db.add(db_section)
    await db.commit()
    await db.refresh(db_section)
    return db_section


async def delete_section(db: AsyncSession, section_id: int) -> Optional[models.Section]:
    db_section = await get_section(db, section_id)
    if db_section:
        await db.delete(db_section)
        await db.commit()
    return db_section


async def delete_sections_by_proposal_id(db: AsyncSession, proposal_id: int) -> None:
    await db.execute(models.Section.__table__.delete().where(models.Section.proposal_id == proposal_id))
    await db.commit()


async def reorder_sections(db: AsyncSession, reorder_requests: List[schemas.ReorderSection]) -> bool:
    for reorder_request in reorder_requests:
        db_section = await get_section(db, reorder_request.sectionId)
        if db_section:
            db_section.order = reorder_request.newOrder
    await db.commit()
    return True


