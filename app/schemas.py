from typing import List, Optional, Dict
from pydantic import BaseModel
from datetime import date, datetime
from enum import Enum

class PaymentType(str, Enum):
    one_time = "one-time"
    monthly = "monthly"
    recurring = "recurring"

class ImageObject(BaseModel):
    url: str
    alt: Optional[str] = None
    placement: Optional[str] = None

class Image(BaseModel):
    id: int
    url: str

    class Config:
        from_attributes = True

class ImageCreate(BaseModel):
    url: str
    alt: Optional[str] = None
    placement: Optional[str] = None

class ImageDelete(BaseModel):
    id: int

class UserImageBase(BaseModel):
    url: str

class UserImageCreate(UserImageBase):
    pass

class UserImage(UserImageBase):
    id: int

    class Config:
        from_attributes = True

class ImageDisplay(BaseModel):
    id: int
    url: str
    alt: Optional[str] = None
    placement: Optional[str] = None

class SectionBase(BaseModel):
    title: str
    contentHtml: Optional[str] = None
    order: Optional[int] = None
    image_urls: Optional[List[str]] = []  # Raw list persisted in DB
    images: Optional[List[ImageDisplay]] = []  # Derived / transformed list with metadata
    image_placement: Optional[str] = None
    mermaid_chart: Optional[str] = None
    chart_type: Optional[str] = None
    tech_logos: Optional[List[Dict]] = []
    custom_logos: Optional[List[Dict]] = []


class SectionCreate(SectionBase):
    order: Optional[int] = None

class Section(SectionBase):
    id: int
    proposal_id: int

    class Config:
        from_attributes = True

class ProposalBase(BaseModel):
    clientName: str
    rfpText: str
    totalAmount: float
    paymentType: PaymentType
    numDeliverables: int
    startDate: date
    endDate: date
    companyName: str
    companyLogoUrl: str
    companyContact: str

class ProposalCreate(ProposalBase):
    pass

class ProposalUpdate(BaseModel):
    clientName: Optional[str] = None
    rfpText: Optional[str] = None
    totalAmount: Optional[float] = None
    paymentType: Optional[PaymentType] = None
    numDeliverables: Optional[int] = None
    startDate: Optional[date] = None
    endDate: Optional[date] = None
    companyName: Optional[str] = None
    companyLogoUrl: Optional[str] = None
    companyContact: Optional[str] = None

class Proposal(ProposalBase):
    id: int
    sections: List[Section] = []

    class Config:
        from_attributes = True

class SectionUpdate(BaseModel):
    title: Optional[str] = None
    contentHtml: Optional[str] = None
    image_urls: Optional[List[str]] = None
    images: Optional[List[ImageDisplay]] = None  # Accept images if frontend sends objects; converted to image_urls in CRUD
    image_placement: Optional[str] = None
    mermaid_chart: Optional[str] = None
    chart_type: Optional[str] = None
    layout: Optional[str] = None

class ReorderSection(BaseModel):
    sectionId: int
    newOrder: int

class GenerateContentRequest(BaseModel):
    section_id: int
    keywords: str

class GenerateProposalDraftRequest(BaseModel):
    sections: List[str]

class GenerateChartForSectionRequest(BaseModel):
    section_id: int
    description: str
    chart_type: str

class EnhanceSectionRequest(BaseModel):
    section_id: int
    enhancement_type: str
    instructions: Optional[str] = None
    tone: Optional[str] = "professional"
    focus_points: Optional[List[str]] = None
