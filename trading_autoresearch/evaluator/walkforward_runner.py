"""
Walk-forward (rolling OOS) evaluation runner.

Splits the evaluation period into rolling train/test windows
and reports per-window and aggregate OOS metrics.

The actual backtest execution happens via BacktestRunner (subprocess).
"""

from __future__ import annotations

import logging
from types_ import WalkForwardMetrics

log = logging.getLogger(__name__)


class WalkForwardRunner:
    """
    Runs rolling walk-forward evaluation.

    Each window:
      - Train on N days
      - Test (OOS) on M days
      - Record OOS Sharpe

    Returns aggregate statistics across all OOS windows.
    """

    def __init__(self, config):
        self.config = config
        self.train_days = getattr(config, "wf_train_days", 90)
        self.test_days = getattr(config, "wf_test_days", 30)
        self.n_windows = getattr(config, "wf_n_windows", 8)

    def run(self, strategy_path) -> WalkForwardMetrics:
        """
        Run walk-forward evaluation.

        TODO: Wire to BacktestRunner with date-range parameters.
        This is the integration point — each window calls
        backtest_runner.run_isolated() with constrained date ranges.
        """
        log.info(
            "Walk-forward: %d windows, %dd train / %dd test",
            self.n_windows,
            self.train_days,
            self.test_days,
        )

        # Placeholder — replace with actual per-window backtest calls
        per_window_sharpe: list[float] = []

        # In production, this loop would:
        # for window_idx in range(self.n_windows):
        #     train_start = base_date + (window_idx * step)
        #     train_end = train_start + train_days
        #     test_end = train_end + test_days
        #     metrics = backtest_runner.run_window(strategy_path, train_start, train_end, test_end)
        #     per_window_sharpe.append(metrics.sharpe)

        if not per_window_sharpe:
            return WalkForwardMetrics()

        import numpy as np

        return WalkForwardMetrics(
            mean_oos_sharpe=float(np.mean(per_window_sharpe)),
            std_oos_sharpe=float(np.std(per_window_sharpe)),
            pct_positive_windows=float(
                sum(1 for s in per_window_sharpe if s > 0) / len(per_window_sharpe)
            ),
            num_windows=len(per_window_sharpe),
            per_window_sharpe=per_window_sharpe,
        )
