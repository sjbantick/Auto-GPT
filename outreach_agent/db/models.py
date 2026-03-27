import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from outreach_agent.db.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    product_description = Column(Text, nullable=False)
    status = Column(String, default="draft")  # draft, generating, ready
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    prospects = relationship("Prospect", back_populates="campaign", cascade="all, delete-orphan")


class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    name = Column(String, nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, default="")
    industry = Column(String, default="")
    linkedin_url = Column(String, default="")
    email = Column(String, default="")
    notes = Column(Text, default="")
    status = Column(String, default="pending")  # pending, researched, generated
    research_data = Column(Text, default="")  # JSON blob from researcher agent
    strategy_data = Column(Text, default="")  # JSON blob from strategist agent
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    campaign = relationship("Campaign", back_populates="prospects")
    messages = relationship("Message", back_populates="prospect", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False)
    channel = Column(String, nullable=False)  # email, linkedin, follow_up_email
    sequence_order = Column(Integer, nullable=False)  # 1, 2, 3...
    send_day = Column(Integer, nullable=False)  # day 1, day 3, day 7...
    variant = Column(String, default="A")  # A or B
    subject = Column(String, default="")  # for emails
    body = Column(Text, nullable=False)
    status = Column(String, default="draft")  # draft, sent, replied
    selected = Column(Integer, default=0)  # 1 if this variant was selected as winner
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    prospect = relationship("Prospect", back_populates="messages")
