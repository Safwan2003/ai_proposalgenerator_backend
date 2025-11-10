
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, Table, Float, Date, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from .database import Base
import datetime

class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, index=True)
    clientName = Column(String(255), index=True)
    rfpText = Column(Text)
    totalAmount = Column(Float)
    paymentType = Column(String(50))
    numDeliverables = Column(Integer)
    startDate = Column(Date)
    endDate = Column(Date)
    companyName = Column(String(255))
    companyLogoUrl = Column(String(255))
    companyContact = Column(String(255))
    custom_css = Column(Text, nullable=True)

    sections = relationship("Section", back_populates="proposal", cascade="all, delete-orphan")

class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True)
    contentHtml = Column(Text)
    order = Column(Integer)
    image_urls = Column(JSON, nullable=True, default=[])
    image_placement = Column(String(50), nullable=True)
    mermaid_chart = Column(Text, nullable=True)
    layout = Column(String(50), nullable=True)

    chart_type = Column(String(50), nullable=True)
    tech_logos = Column(JSON, nullable=True)
    custom_logos = Column(JSON, nullable=True)

    proposal_id = Column(Integer, ForeignKey("proposals.id"))
    proposal = relationship("Proposal", back_populates="sections")

class UserImage(Base):
    __tablename__ = "user_images"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
