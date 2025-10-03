from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
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
    image_placement = Column(String(50), nullable=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"))

    proposal = relationship("Proposal", back_populates="sections")
    images = relationship("Image", back_populates="section", cascade="all, delete-orphan")
    versions = relationship("SectionVersion", back_populates="section", cascade="all, delete-orphan")

    @property
    def image_urls(self):
        return [image.url for image in self.images]

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255))
    section_id = Column(Integer, ForeignKey("sections.id"))

    section = relationship("Section", back_populates="images")

class SectionVersion(Base):
    __tablename__ = "section_versions"

    id = Column(Integer, primary_key=True, index=True)
    contentHtml = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    section_id = Column(Integer, ForeignKey("sections.id"))

    section = relationship("Section", back_populates="versions")