# Sales Outreach Agent-as-a-Service — Build Plan

## Overview
A multi-agent sales outreach platform that researches prospects, develops personalized strategies, and generates multi-channel outreach sequences (cold email, follow-ups, LinkedIn). Built as a FastAPI service with a web UI, targeting agency services use cases.

## Architecture

### Multi-Agent Pipeline
```
Input (prospect + product) → Researcher → Strategist → Copywriter → Output (campaign sequence)
```

- **Researcher Agent**: Gathers prospect intel — company info, recent news, pain points, industry context
- **Strategist Agent**: Analyzes research, identifies hooks/angles, selects tone & approach, plans sequence timing
- **Copywriter Agent**: Generates personalized messages per channel (email, LinkedIn, follow-ups) with A/B variants

### Tech Stack
- **Backend**: Python, FastAPI, SQLite (via SQLAlchemy), anthropic SDK
- **Frontend**: Single-page HTML/JS app (no framework — fast to build)
- **AI**: Claude API with mock fallback (works without API key)

## File Structure
```
outreach_agent/
├── main.py                  # FastAPI app, mounts static files, includes routers
├── config.py                # Settings, env vars, mock mode toggle
├── requirements.txt         # Dependencies
│
├── agents/
│   ├── __init__.py
│   ├── researcher.py        # Prospect research agent
│   ├── strategist.py        # Outreach strategy agent
│   ├── copywriter.py        # Message generation agent
│   └── pipeline.py          # Orchestrates all 3 agents end-to-end
│
├── llm.py                   # Claude API client + mock mode
│
├── db/
│   ├── __init__.py
│   ├── database.py          # SQLAlchemy engine, session, Base
│   └── models.py            # ORM models: Campaign, Prospect, Message, Sequence
│
├── schemas.py               # Pydantic request/response models
│
├── api/
│   ├── __init__.py
│   ├── campaigns.py         # POST /campaigns, GET /campaigns, GET /campaigns/{id}
│   ├── prospects.py         # CRUD prospects within campaigns
│   ├── generate.py          # POST /generate — triggers the agent pipeline
│   └── analytics.py         # GET /analytics — campaign stats, A/B performance
│
└── static/
    ├── index.html           # Main SPA shell
    ├── app.js               # Frontend logic — campaign builder, results viewer, analytics
    └── styles.css           # Clean, modern styling
```

## Build Order (7 phases)

### Phase 1: Foundation
- `config.py` — env vars, settings, mock mode detection
- `requirements.txt` — fastapi, uvicorn, anthropic, sqlalchemy, pydantic
- `db/database.py` — SQLite setup
- `db/models.py` — Campaign, Prospect, Message, Sequence tables
- `schemas.py` — Pydantic models

### Phase 2: LLM Layer
- `llm.py` — `generate()` function that calls Claude or returns mock data based on config
- Mock responses are realistic agency outreach examples, not lorem ipsum

### Phase 3: Agent Pipeline
- `agents/researcher.py` — takes prospect info, returns structured research (pain points, news, hooks)
- `agents/strategist.py` — takes research, returns strategy (angles, tone, sequence plan, timing)
- `agents/copywriter.py` — takes strategy, returns messages per channel with A/B variants
- `agents/pipeline.py` — chains all 3, stores results in DB

### Phase 4: REST API
- `api/campaigns.py` — create/list/get campaigns with product description
- `api/prospects.py` — add prospects to campaigns
- `api/generate.py` — trigger pipeline for a prospect, return generated sequence
- `api/analytics.py` — campaign stats, message counts, variant performance

### Phase 5: FastAPI App
- `main.py` — wire up routers, static files, CORS, startup DB init

### Phase 6: Frontend
- `static/index.html` — layout with sidebar nav (Campaigns, Analytics)
- `static/styles.css` — modern dark theme, cards, tables
- `static/app.js` — campaign CRUD, prospect entry, generate trigger, results display, analytics charts

### Phase 7: Polish
- Seed data / demo mode
- Error handling on API + frontend
- Campaign status tracking (draft → generating → ready)
- Message status (draft → sent → replied)

## Key Design Decisions
1. **Mock mode**: When `ANTHROPIC_API_KEY` is not set, returns pre-built realistic mock responses. Toggled via env var.
2. **A/B variants**: Copywriter generates 2 variants per message. Frontend shows both with "select winner" UI.
3. **Sequence timing**: Strategist plans a multi-touch sequence (day 1: cold email, day 3: LinkedIn, day 7: follow-up, etc.)
4. **Agency focus**: Default prompts tuned for selling agency services (marketing, consulting, creative). User can override product description.
