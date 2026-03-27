from __future__ import annotations

import json

from sqlalchemy.orm import Session

from outreach_agent.agents.copywriter import write_copy
from outreach_agent.agents.researcher import research
from outreach_agent.agents.strategist import strategize
from outreach_agent.db.models import Message, Prospect


def run_pipeline(prospect: Prospect, product_description: str, db: Session) -> list[Message]:
    """Run the full agent pipeline: research → strategize → write copy → save messages."""

    # Step 1: Research
    research_data = research(
        prospect_name=prospect.name,
        company=prospect.company,
        role=prospect.role,
        industry=prospect.industry,
        notes=prospect.notes,
        product_description=product_description,
    )
    prospect.research_data = json.dumps(research_data)
    prospect.status = "researched"
    db.commit()

    # Step 2: Strategize
    strategy_data = strategize(research_data, product_description)
    prospect.strategy_data = json.dumps(strategy_data)
    db.commit()

    # Step 3: Write copy
    copy_data = write_copy(research_data, strategy_data, prospect.name)

    # Step 4: Save messages to DB
    messages = []
    for msg_data in copy_data.get("messages", []):
        msg = Message(
            prospect_id=prospect.id,
            channel=msg_data.get("channel", "email"),
            sequence_order=msg_data.get("sequence_order", 1),
            send_day=msg_data.get("send_day", 1),
            variant=msg_data.get("variant", "A"),
            subject=msg_data.get("subject", ""),
            body=msg_data.get("body", ""),
        )
        db.add(msg)
        messages.append(msg)

    prospect.status = "generated"
    db.commit()

    for msg in messages:
        db.refresh(msg)

    return messages
