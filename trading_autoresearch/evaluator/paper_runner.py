"""
Paper/replay stage runner.

Wraps the paper trading adapter and collects a PaperStageReport.
"""

from __future__ import annotations

import logging
from pathlib import Path

from adapters.paper_adapter import PaperAdapter
from types_ import PaperStageReport

log = logging.getLogger(__name__)


class PaperRunner:
    def __init__(self, config=None):
        self.adapter = PaperAdapter()
        self.duration_days = getattr(config, "paper_duration_days", 30)
        self.latency_ms = getattr(config, "paper_latency_ms", 200)

    def run(self, strategy_path: Path) -> PaperStageReport:
        log.info("Running paper stage for %s (%dd)", strategy_path, self.duration_days)
        return self.adapter.run(
            strategy_path,
            duration_days=self.duration_days,
            latency_ms=self.latency_ms,
        )
