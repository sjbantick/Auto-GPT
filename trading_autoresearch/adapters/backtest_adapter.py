"""
Adapter interface for your backtest engine.

Replace run_from_params() with a call to your actual engine
(vectorbt, backtrader, backtesting.py, or custom).

This stub returns synthetic results so the framework can run
end-to-end without a real engine installed.

The adapter returns JSON-serializable dicts so results can cross
the subprocess boundary safely.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class BacktestAdapter:
    """
    Plug your engine here.

    The run_from_params method is called from an isolated subprocess.
    It must return a plain dict (JSON-serializable).
    """

    def run_from_params(
        self,
        strategy_path: Path,
        symbols: list[str],
        days: int,
        fee_pct: float,
        slippage_pct: float,
        mode: str,
    ) -> dict:
        """
        Run backtest and return results as a dict.

        Replace the stub below with your actual engine call.
        The dict must contain these keys:
          - trades_json: JSON string of trades DataFrame
          - daily_pnl_json: JSON string of daily PnL series
          - per_symbol_sharpe_json: JSON string of {symbol: sharpe}
          - num_symbols: int
          - strategy_path: str
          - fee_total: float
          - gross_profit: float
          - regime_metrics_json: JSON string of {bull_sharpe, bear_sharpe, sideways_sharpe}
          - error: null if OK, string if failed
        """
        import numpy as np
        import pandas as pd

        rng = np.random.default_rng(seed=42)
        n_trades = int(rng.integers(40, 200))
        n_days = days

        returns = rng.normal(0.002, 0.015, n_trades) - fee_pct - slippage_pct
        trades_df = pd.DataFrame(
            {
                "entry_time": pd.date_range(
                    "2023-01-01", periods=n_trades, freq="D"
                ).astype(str).tolist(),
                "exit_time": pd.date_range(
                    "2023-01-02", periods=n_trades, freq="D"
                ).astype(str).tolist(),
                "return_pct": returns.tolist(),
                "hold_minutes": rng.integers(5, 480, n_trades).tolist(),
            }
        )

        daily_pnl = rng.normal(0.001, 0.012, n_days).tolist()

        per_symbol_sharpe = {s: float(rng.normal(1.0, 0.5)) for s in symbols}
        gross_profit = float(max(returns[returns > 0].sum(), 0.001))
        fee_total = float(fee_pct * n_trades)

        regime_metrics = {
            "bull_sharpe": float(rng.normal(1.2, 0.3)),
            "bear_sharpe": float(rng.normal(0.3, 0.5)),
            "sideways_sharpe": float(rng.normal(0.8, 0.4)),
        }

        return {
            "trades_json": trades_df.to_json(),
            "daily_pnl_json": json.dumps(daily_pnl),
            "per_symbol_sharpe_json": json.dumps(per_symbol_sharpe),
            "num_symbols": len(symbols),
            "strategy_path": str(strategy_path),
            "fee_total": fee_total,
            "gross_profit": gross_profit,
            "regime_metrics_json": json.dumps(regime_metrics),
            "error": None,
        }
