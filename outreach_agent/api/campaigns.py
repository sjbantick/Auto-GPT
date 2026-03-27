from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from outreach_agent.db.database import get_db
from outreach_agent.db.models import Campaign
from outreach_agent.schemas import CampaignCreate, CampaignOut

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("", response_model=CampaignOut)
def create_campaign(data: CampaignCreate, db: Session = Depends(get_db)):
    campaign = Campaign(name=data.name, product_description=data.product_description)
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _enrich(campaign)


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return [_enrich(c) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _enrich(campaign)


@router.delete("/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"ok": True}


def _enrich(campaign: Campaign) -> dict:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "product_description": campaign.product_description,
        "status": campaign.status,
        "created_at": campaign.created_at,
        "prospect_count": len(campaign.prospects),
    }
