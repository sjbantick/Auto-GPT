"""
Central definition of editable vs forbidden paths.

Imported by constraints.py and anywhere else that needs path policy.
"""

from __future__ import annotations

# Paths the agent may modify
EDITABLE_ROOTS: tuple[str, ...] = (
    "strategies/",
    "features/",
    "research_configs/",
    "scoring/",
)

# Paths the agent must never touch
FORBIDDEN_ROOTS: tuple[str, ...] = (
    "execution/",
    "brokers/",
    "exchange/",
    "auth/",
    "infra/",
    "deployment/",
    "secrets/",
    "risk_core/",
    "orchestrator/",
    "sandbox/",
    "evaluator/",
    "adapters/",
    "reports/",
    "configs/",
    ".env",
    ".autoresearch_lock",
)

# Import patterns that must never appear in candidate code
FORBIDDEN_IMPORT_PATTERNS: tuple[str, ...] = (
    r"^import\s+execution\b",
    r"^from\s+execution\b",
    r"^import\s+brokers\b",
    r"^from\s+brokers\b",
    r"^import\s+auth\b",
    r"^from\s+auth\b",
    r"^import\s+risk_core\b",
    r"^from\s+risk_core\b",
    r"^import\s+infra\b",
    r"^from\s+infra\b",
    r"^import\s+deployment\b",
    r"^from\s+deployment\b",
    r"^import\s+secrets\b",
    r"^from\s+secrets\b",
)

MAX_PATCH_LINES = 200
MAX_NEW_FILES = 3
