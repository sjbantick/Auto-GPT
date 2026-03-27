import os


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MOCK_MODE = not bool(ANTHROPIC_API_KEY)
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./outreach.db")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
