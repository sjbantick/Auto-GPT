from __future__ import annotations

import datetime

from pydantic import BaseModel


# --- Campaign ---
class CampaignCreate(BaseModel):
    name: str
    product_description: str


class CampaignOut(BaseModel):
    id: int
    name: str
    product_description: str
    status: str
    created_at: datetime.datetime
    prospect_count: int = 0

    model_config = {"from_attributes": True}


# --- Prospect ---
class ProspectCreate(BaseModel):
    name: str
    company: str
    role: str = ""
    industry: str = ""
    linkedin_url: str = ""
    email: str = ""
    notes: str = ""


class ProspectOut(BaseModel):
    id: int
    campaign_id: int
    name: str
    company: str
    role: str
    industry: str
    linkedin_url: str
    email: str
    notes: str
    status: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- Message ---
class MessageOut(BaseModel):
    id: int
    prospect_id: int
    channel: str
    sequence_order: int
    send_day: int
    variant: str
    subject: str
    body: str
    status: str
    selected: int
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# --- Generate ---
class GenerateRequest(BaseModel):
    prospect_id: int


class GenerateResponse(BaseModel):
    prospect_id: int
    status: str
    messages: list[MessageOut]


# --- Analytics ---
class CampaignAnalytics(BaseModel):
    campaign_id: int
    campaign_name: str
    total_prospects: int
    prospects_generated: int
    total_messages: int
    messages_by_channel: dict[str, int]
    messages_by_status: dict[str, int]
