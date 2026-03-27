from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from outreach_agent.agents.pipeline import run_pipeline
from outreach_agent.db.database import get_db
from outreach_agent.db.models import Campaign, Message, Prospect
from outreach_agent.schemas import GenerateResponse, MessageOut

router = APIRouter(prefix="/api/generate", tags=["generate"])


@router.post("/{prospect_id}", response_model=GenerateResponse)
def generate_outreach(prospect_id: int, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    campaign = db.query(Campaign).filter(Campaign.id == prospect.campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Clear existing messages if re-generating
    db.query(Message).filter(Message.prospect_id == prospect_id).delete()
    db.commit()

    campaign.status = "generating"
    db.commit()

    messages = run_pipeline(prospect, campaign.product_description, db)

    # Update campaign status
    campaign.status = "ready"
    db.commit()

    return GenerateResponse(
        prospect_id=prospect_id,
        status="generated",
        messages=[MessageOut.model_validate(m) for m in messages],
    )
