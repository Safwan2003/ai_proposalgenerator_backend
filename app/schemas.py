from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from enum import Enum

class PaymentType(str, Enum):
    one_time = "one-time"
    monthly = "monthly"
    recurring = "recurring"

class Image(BaseModel):
    id: int
    url: str

    class Config:
        from_attributes = True

class SectionVersion(BaseModel):
    id: int
    contentHtml: str
    created_at: datetime

    class Config:
        from_attributes = True

class SectionBase(BaseModel):
    title: str
    contentHtml: str
    order: int
    image_placement: Optional[str] = None

class SectionCreate(SectionBase):
    images: List[str] = []

class Section(SectionBase):
    id: int
    image_urls: List[str]
    versions: List[SectionVersion] = []

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

class Proposal(ProposalBase):
    id: int
    sections: List[Section] = []
    custom_css: Optional[str] = None

    class Config:
        from_attributes = True

class SectionUpdate(BaseModel):
    title: Optional[str] = None
    contentHtml: Optional[str] = None
    image_placement: Optional[str] = None

class ReorderSection(BaseModel):
    sectionId: int
    newOrder: int

class GenerateContentRequest(BaseModel):
    section_id: int
    keywords: str

class DesignSuggestion(BaseModel):
    prompt: str
    css: str

class ImageCreate(BaseModel):
    url: str

class ImageDelete(BaseModel):
    url: str