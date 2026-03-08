"""Ranked candidate leaderboard. Reads from the candidate registry."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from orchestrator.candidate_registry import CandidateRegistry
from types_ import CandidateStatus

log = logging.getLogger(__name__)


class Leaderboard:
    def __init__(self, registry: CandidateRegistry):
        self.registry = registry

    def print_top(self, n: int = 10) -> str:
        """Return a markdown table of the top N candidates by OOS Sharpe."""
        all_candidates = []
        for status in (
            CandidateStatus.APPROVED,
            CandidateStatus.LIVE_PROBATION,
            CandidateStatus.PAPER_APPROVED,
            CandidateStatus.PAPER_CANDIDATE,
        ):
            all_candidates.extend(self.registry.list_by_status(status))

        # Sort by OOS Sharpe descending
        def sort_key(c):
            try:
                deltas = json.loads(c.get("metric_deltas_json", "{}"))
                return deltas.get("oos_sharpe_candidate", 0.0)
            except Exception:
                return 0.0

        all_candidates.sort(key=sort_key, reverse=True)

        lines = [
            "| Rank | Run ID | Status | OOS Sharpe | Hypothesis |",
            "|---|---|---|---|---|",
        ]
        for i, c in enumerate(all_candidates[:n], 1):
            try:
                deltas = json.loads(c.get("metric_deltas_json", "{}"))
                oos = deltas.get("oos_sharpe_candidate", 0.0)
            except Exception:
                oos = 0.0
            hyp = (c.get("hypothesis") or "")[:60]
            lines.append(
                f"| {i} | {c['run_id']} | {c['status']} | {oos:.3f} | {hyp} |"
            )

        return "\n".join(lines)
