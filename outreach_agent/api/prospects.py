from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from outreach_agent.db.database import get_db
from outreach_agent.db.models import Campaign, Message, Prospect
from outreach_agent.schemas import MessageOut, ProspectCreate, ProspectOut

router = APIRouter(prefix="/api/campaigns/{campaign_id}/prospects", tags=["prospects"])


@router.post("", response_model=ProspectOut)
def add_prospect(campaign_id: int, data: ProspectCreate, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    prospect = Prospect(campaign_id=campaign_id, **data.model_dump())
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return prospect


@router.get("", response_model=list[ProspectOut])
def list_prospects(campaign_id: int, db: Session = Depends(get_db)):
    return db.query(Prospect).filter(Prospect.campaign_id == campaign_id).order_by(Prospect.created_at.desc()).all()


@router.get("/{prospect_id}", response_model=ProspectOut)
def get_prospect(campaign_id: int, prospect_id: int, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id, Prospect.campaign_id == campaign_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect


@router.get("/{prospect_id}/messages", response_model=list[MessageOut])
def get_prospect_messages(campaign_id: int, prospect_id: int, db: Session = Depends(get_db)):
    return db.query(Message).filter(Message.prospect_id == prospect_id).order_by(Message.sequence_order, Message.variant).all()


@router.delete("/{prospect_id}")
def delete_prospect(campaign_id: int, prospect_id: int, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id, Prospect.campaign_id == campaign_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    db.delete(prospect)
    db.commit()
    return {"ok": True}
