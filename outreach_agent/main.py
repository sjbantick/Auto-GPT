import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from outreach_agent.api import analytics, campaigns, generate, prospects
from outreach_agent.config import HOST, MOCK_MODE, PORT
from outreach_agent.db.database import init_db


@asynccontextmanager
async def lifespan(app):
    init_db()
    mode = "MOCK" if MOCK_MODE else "LIVE (Claude API)"
    print(f"\n{'='*50}")
    print(f"  Outreach Agent — {mode} mode")
    print(f"  http://{HOST}:{PORT}")
    print(f"{'='*50}\n")
    yield


app = FastAPI(title="Outreach Agent", description="AI-powered sales outreach agent-as-a-service", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(campaigns.router)
app.include_router(prospects.router)
app.include_router(generate.router)
app.include_router(analytics.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("outreach_agent.main:app", host=HOST, port=PORT, reload=True)
