from __future__ import annotations

import json

from outreach_agent.llm import generate

SYSTEM_PROMPT = """You are an expert B2B sales copywriter agent. Given a strategy and research, you write personalized outreach messages for each touchpoint in the sequence.

You MUST return valid JSON with this exact structure:
{
    "messages": [
        {
            "sequence_order": 1,
            "channel": "email",
            "send_day": 1,
            "variant": "A",
            "subject": "Email subject line (empty string for LinkedIn)",
            "body": "The message body. Use {{name}} for prospect name and {{sender}} for sender name."
        },
        {
            "sequence_order": 1,
            "channel": "email",
            "send_day": 1,
            "variant": "B",
            "subject": "Alternative subject line",
            "body": "Alternative message body — different angle or style."
        }
    ]
}

Rules:
- Generate TWO variants (A and B) for EACH touchpoint in the sequence
- Variant A should follow the primary angle, Variant B the secondary angle
- Keep emails under 150 words. LinkedIn messages under 100 words.
- No generic filler. Every sentence should earn its place.
- Use {{name}} and {{sender}} as placeholders.
- Subject lines for follow-ups should thread naturally (Re: original subject)."""


def write_copy(research_data: dict, strategy_data: dict, prospect_name: str) -> dict:
    user_prompt = f"""Write personalized outreach messages for this prospect.

**Prospect name:** {prospect_name}

**Research:**
{json.dumps(research_data, indent=2)}

**Strategy:**
{json.dumps(strategy_data, indent=2)}

Write A/B variants for each touchpoint in the sequence. Return JSON only."""

    response = generate(SYSTEM_PROMPT, user_prompt)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"raw_copy": response}
