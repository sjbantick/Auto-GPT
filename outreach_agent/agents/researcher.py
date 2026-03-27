from __future__ import annotations

import json

from outreach_agent.llm import generate

SYSTEM_PROMPT = """You are an expert B2B sales researcher agent. Your job is to research a prospect and their company to find actionable intelligence for a sales outreach campaign.

You MUST return valid JSON with this exact structure:
{
    "company_overview": "2-3 sentence summary of the company",
    "recent_news": ["news item 1", "news item 2", "news item 3"],
    "pain_points": ["pain point 1", "pain point 2", "pain point 3"],
    "industry_trends": ["trend 1", "trend 2"],
    "hooks": ["personalization hook 1", "hook 2", "hook 3"],
    "decision_maker_profile": "Brief profile of the prospect's likely priorities and communication style"
}

Focus on finding SPECIFIC, ACTIONABLE intelligence — not generic industry info. The hooks should be things a salesperson can reference in a cold email to show they've done their homework."""


def research(prospect_name: str, company: str, role: str, industry: str, notes: str, product_description: str) -> dict:
    user_prompt = f"""Research this prospect for a sales outreach campaign:

**Prospect:** {prospect_name}
**Company:** {company}
**Role:** {role}
**Industry:** {industry}
**Additional context:** {notes}

**We are selling:** {product_description}

Find specific intelligence about their company, recent activity, pain points, and personalization hooks that we can use in outreach. Return JSON only."""

    response = generate(SYSTEM_PROMPT, user_prompt)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"raw_research": response}
