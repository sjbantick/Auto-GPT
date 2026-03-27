from __future__ import annotations

import json

import outreach_agent.config as config


def generate(system_prompt: str, user_prompt: str) -> str:
    if config.MOCK_MODE:
        return _mock_generate(system_prompt, user_prompt)
    return _real_generate(system_prompt, user_prompt)


def _real_generate(system_prompt: str, user_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=config.MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _mock_generate(system_prompt: str, user_prompt: str) -> str:
    """Return realistic mock responses based on which agent is calling."""
    sp = system_prompt.lower()

    # Order matters: check most specific first since prompts contain overlapping keywords
    if "copywriter" in sp:
        return json.dumps({
            "messages": [
                {
                    "sequence_order": 1, "channel": "email", "send_day": 1, "variant": "A",
                    "subject": "Your TikTok expansion + a thought on scaling creative",
                    "body": "Hi {{name}},\n\nSaw the news about your TikTok creator partnership \u2014 congrats. That's a smart move given where D2C attention is shifting.\n\nI caught your CEO's AdWorld talk on AI in ad creative, and it got me thinking: most agencies I talk to are spending 40%+ of their creative team's time on platform-specific asset adaptation. The ones pulling ahead are automating that entirely.\n\nWe help agencies like yours produce personalized ad creative at 10x the speed \u2014 without sacrificing the quality that won you that 3.2x ROAS for your skincare client.\n\nWorth a 15-min call to see if there's a fit?\n\nBest,\n{{sender}}"
                },
                {
                    "sequence_order": 1, "channel": "email", "send_day": 1, "variant": "B",
                    "subject": "Quick question about your creative workflow",
                    "body": "Hi {{name}},\n\nI work with performance marketing agencies scaling their creative output \u2014 and your team's work on D2C paid social caught my eye.\n\nCurious: as you expand into TikTok creator campaigns, how are you handling the creative adaptation across platforms? Most agencies I talk to say it's their biggest bottleneck.\n\nWe've helped similar shops cut creative production time by 70% while actually improving ROAS. Happy to share how if useful.\n\n{{sender}}"
                },
                {
                    "sequence_order": 2, "channel": "linkedin", "send_day": 3, "variant": "A",
                    "subject": "",
                    "body": "Hi {{name}} \u2014 enjoyed your CEO's take on AI x ad creative at AdWorld. We're seeing the same shift across our agency clients.\n\nJust published a piece on how top agencies are using AI to scale creative without growing headcount. Thought it might be relevant given your TikTok expansion. Happy to share if you're interested."
                },
                {
                    "sequence_order": 2, "channel": "linkedin", "send_day": 3, "variant": "B",
                    "subject": "",
                    "body": "Hi {{name}} \u2014 your team's D2C performance work is impressive, especially that 3.2x ROAS case study.\n\nWe help agencies like yours automate the creative production side so your strategists can focus on what actually moves ROAS. Would love to connect and swap notes."
                },
                {
                    "sequence_order": 3, "channel": "follow_up_email", "send_day": 7, "variant": "A",
                    "subject": "Re: Your TikTok expansion + a thought on scaling creative",
                    "body": "Hi {{name}},\n\nQuick follow-up \u2014 thought you might find this relevant.\n\nWe just wrapped a project with a performance agency similar to yours (paid social focus, 40-person team). They were spending ~30 hours/week on cross-platform creative adaptation. We got that down to 4 hours.\n\nThe result: they took on 3 new clients without hiring, and their average ROAS improved 22% because their strategists had more time for actual optimization.\n\nWould a quick case study walkthrough be useful?\n\n{{sender}}"
                },
                {
                    "sequence_order": 3, "channel": "follow_up_email", "send_day": 7, "variant": "B",
                    "subject": "Re: Quick question about your creative workflow",
                    "body": "Hi {{name}},\n\nCircling back \u2014 I know timing isn't always right.\n\nOne thing that might be useful regardless: we put together a benchmark report on creative production efficiency across 50+ agencies. The data on how top performers handle cross-platform adaptation is eye-opening.\n\nHappy to send it over, no strings attached.\n\n{{sender}}"
                },
                {
                    "sequence_order": 4, "channel": "follow_up_email", "send_day": 14, "variant": "A",
                    "subject": "Should I close the loop?",
                    "body": "Hi {{name}},\n\nI've reached out a couple times and want to be respectful of your time. I'll assume the timing isn't right and close the loop on my end.\n\nIf scaling creative production becomes a priority down the road, I'm here. Just reply to this thread.\n\nWishing you and the team a strong Q2.\n\n{{sender}}"
                },
                {
                    "sequence_order": 4, "channel": "follow_up_email", "send_day": 14, "variant": "B",
                    "subject": "Last note from me",
                    "body": "Hi {{name}},\n\nLast note from me \u2014 I know agency life is hectic, especially mid-TikTok expansion.\n\nIf you ever want to explore how to scale creative output without scaling headcount, I'd love to help. No pressure, no pitch \u2014 just a conversation.\n\nAll the best,\n{{sender}}"
                }
            ]
        })

    if "strategist" in sp:
        return json.dumps({
            "approach": "Challenger Sale \u2014 lead with an insight about their industry, not a pitch",
            "tone": "Confident but not pushy. Peer-to-peer, not vendor-to-buyer. Reference their specific work.",
            "primary_angle": "Their CEO already sees AI as the future of ad creative \u2014 we're the tool that makes that vision real, today.",
            "secondary_angle": "Their scaling pain with cross-platform creative is exactly what our automation solves. Lead with the 3.2x ROAS case study parallel.",
            "sequence": [
                {"order": 1, "channel": "email", "day": 1, "goal": "Pattern interrupt \u2014 lead with insight about their TikTok expansion + AI creative angle"},
                {"order": 2, "channel": "linkedin", "day": 3, "goal": "Warm touch \u2014 reference their CEO's AdWorld talk, share relevant content"},
                {"order": 3, "channel": "follow_up_email", "day": 7, "goal": "Value add \u2014 share a mini case study of similar agency getting results"},
                {"order": 4, "channel": "follow_up_email", "day": 14, "goal": "Breakup email \u2014 create urgency, offer specific time for a call"}
            ],
            "personalization_notes": "Reference their TikTok partnership, CEO's AdWorld talk, and the 3.2x ROAS case study. Avoid generic 'agency' language \u2014 use their specific niche terms (D2C, paid social, creator campaigns)."
        })

    if "researcher" in sp:
        return json.dumps({
            "company_overview": "Mid-size digital marketing agency founded in 2019, ~50 employees. Specializes in paid social and performance marketing for D2C brands. Recently expanded into influencer marketing.",
            "recent_news": [
                "Announced a new partnership with TikTok for creator campaigns",
                "Published a case study showing 3.2x ROAS for a skincare brand",
                "Their CEO spoke at AdWorld 2026 about the future of AI in ad creative"
            ],
            "pain_points": [
                "Scaling personalized ad creative across platforms is manual and slow",
                "Client reporting takes significant analyst time each month",
                "Struggling to differentiate from larger agencies on pitch decks"
            ],
            "industry_trends": [
                "Agencies adopting AI tools for creative production at 2x rate YoY",
                "Clients increasingly demanding real-time performance dashboards",
                "Shift from retainer to performance-based pricing models"
            ],
            "hooks": [
                "Their CEO's talk on AI in ad creative \u2014 align with their forward-thinking brand",
                "The scaling pain point maps directly to our automation offering",
                "Their TikTok expansion means they need efficient cross-platform tooling"
            ],
            "decision_maker_profile": "Marketing-savvy, data-driven, likely values efficiency and ROI proof points over feature lists. Responds to case studies and concrete metrics."
        })

    return json.dumps({"response": "Mock response for: " + user_prompt[:100]})
