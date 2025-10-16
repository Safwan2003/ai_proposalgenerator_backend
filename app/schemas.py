from pydantic import BaseModel, Field
from typing import List, Optional, Union
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

class SectionVersion(BaseModel):
    id: int
    contentHtml: str
    created_at: datetime

    class Config:
        from_attributes = True

class SectionBase(BaseModel):
    title: str
    contentHtml: str
    image_placement: Optional[str] = None
    mermaid_chart: Optional[str] = None
    layout: Optional[str] = None

class SectionCreate(SectionBase):
    images: List[ImageObject] = []

class Section(SectionBase):
    id: int
    image_urls: List[str]
    versions: List[SectionVersion] = []
    mermaid_chart: Optional[str] = None
    layout: Optional[str] = None

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
    mermaid_chart: Optional[str] = None
    layout: Optional[str] = None

class ReorderSection(BaseModel):
    sectionId: int
    newOrder: int

class GenerateContentRequest(BaseModel):
    section_id: int
    keywords: str

class DesignSuggestion(BaseModel):
    prompt: str
    css: str

    def __init__(self, **data):
        # Clean any format specifiers in the input data
        if "prompt" in data:
            data["prompt"] = str(data["prompt"]).replace("%", "%%")
        if "css" in data:
            data["css"] = str(data["css"]).replace("%", "%%")
        super().__init__(**data)
        
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Classic Professional",
                "css": "body { font-family: 'Arial', sans-serif; }"
            }
        }

class ImageCreate(BaseModel):
    url: str

class ImageDelete(BaseModel):
    url: str

class GenerateChartRequest(BaseModel):
    description: str
    chart_type: str # 'flowchart' or 'gantt'

class UpdateChartRequest(BaseModel):
    prompt: str
    current_chart_code: str

class GenerateChartForSectionRequest(BaseModel):
    description: str
    chart_type: str

class LiveCustomizeRequest(BaseModel):
    prompt: str
