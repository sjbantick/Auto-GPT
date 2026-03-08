"""
Paper trading / replay adapter.

Plug your event-driven paper trading simulator here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from types_ import PaperStageReport


class PaperAdapter:
    """
    Interface for event-driven paper trading simulation.

    Replace run() with your actual paper trading engine.
    """

    def run(
        self,
        strategy_path: Path,
        duration_days: int = 30,
        latency_ms: int = 200,
    ) -> PaperStageReport:
        # Stub — replace with actual paper sim
        return PaperStageReport(
            num_trades=0,
            fee_adjusted_pf=0.0,
            worst_symbol_drawdown=0.0,
            infra_exceptions=0,
            duration_days=0,
            latency_adjusted_sharpe=0.0,
        )
