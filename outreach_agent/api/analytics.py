from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from outreach_agent.db.database import get_db
from outreach_agent.db.models import Campaign, Message, Prospect
from outreach_agent.schemas import CampaignAnalytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=list[CampaignAnalytics])
def get_analytics(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).all()
    results = []
    for campaign in campaigns:
        prospects = db.query(Prospect).filter(Prospect.campaign_id == campaign.id).all()
        prospect_ids = [p.id for p in prospects]

        total_messages = 0
        by_channel: dict[str, int] = {}
        by_status: dict[str, int] = {}

        if prospect_ids:
            messages = db.query(Message).filter(Message.prospect_id.in_(prospect_ids)).all()
            total_messages = len(messages)
            for m in messages:
                by_channel[m.channel] = by_channel.get(m.channel, 0) + 1
                by_status[m.status] = by_status.get(m.status, 0) + 1

        results.append(CampaignAnalytics(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            total_prospects=len(prospects),
            prospects_generated=len([p for p in prospects if p.status == "generated"]),
            total_messages=total_messages,
            messages_by_channel=by_channel,
            messages_by_status=by_status,
        ))
    return results
