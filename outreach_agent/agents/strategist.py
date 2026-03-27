from __future__ import annotations

import json

from outreach_agent.llm import generate

SYSTEM_PROMPT = """You are an expert B2B sales strategist agent. Given research on a prospect, you design a personalized multi-touch outreach strategy.

You MUST return valid JSON with this exact structure:
{
    "approach": "The sales methodology/approach (e.g., Challenger Sale, consultative, insight-led)",
    "tone": "Description of the tone and voice to use",
    "primary_angle": "The main hook/angle for the outreach",
    "secondary_angle": "Backup angle if the primary doesn't resonate",
    "sequence": [
        {"order": 1, "channel": "email", "day": 1, "goal": "What this touchpoint should achieve"},
        {"order": 2, "channel": "linkedin", "day": 3, "goal": "What this touchpoint should achieve"},
        {"order": 3, "channel": "follow_up_email", "day": 7, "goal": "What this touchpoint should achieve"},
        {"order": 4, "channel": "follow_up_email", "day": 14, "goal": "What this touchpoint should achieve"}
    ],
    "personalization_notes": "Specific things to reference in the copy"
}

Channels must be one of: email, linkedin, follow_up_email.
Design sequences that feel natural, not robotic. Each touchpoint should build on the last."""


def strategize(research_data: dict, product_description: str) -> dict:
    user_prompt = f"""Based on this prospect research, design a multi-touch outreach strategy.

**Research:**
{json.dumps(research_data, indent=2)}

**Product we're selling:** {product_description}

Design a 4-touchpoint outreach sequence with specific angles, tone guidance, and personalization notes. Return JSON only."""

    response = generate(SYSTEM_PROMPT, user_prompt)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"raw_strategy": response}
