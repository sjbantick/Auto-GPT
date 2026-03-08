"""
Backtest runner with subprocess isolation.

Fixes vs v1:
  - Candidate strategy is loaded and evaluated in an ISOLATED subprocess,
    never imported into the orchestrator process
  - Timeout handling on subprocess
  - Results are serialized via JSON across the process boundary
  - Two modes: fast (90d, 1 symbol, no fees) and robust (2y, multi, fees)
  - Slippage stress run at 2x slippage
  - Computes expanded crypto metrics: fee_drag, top-5 PnL, per-symbol Sharpe,
    median hold, regime slices
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from types_ import BacktestMetrics, BacktestRequest, BacktestResult

log = logging.getLogger(__name__)

# Script template that runs inside the isolated subprocess
_SUBPROCESS_SCRIPT = '''
"""Isolated backtest execution. Runs in a separate process."""
import json
import sys
from pathlib import Path

def main():
    request_json = sys.argv[1]
    request = json.loads(request_json)

    strategy_path = Path(request["strategy_path"])
    symbols = request["symbols"]
    days = request["days"]
    fee_pct = request["fee_pct"]
    slippage_pct = request["slippage_pct"]
    mode = request["mode"]

    # Import the backtest adapter (plug your engine here)
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from adapters.backtest_adapter import BacktestAdapter

    adapter = BacktestAdapter()
    result = adapter.run_from_params(
        strategy_path=strategy_path,
        symbols=symbols,
        days=days,
        fee_pct=fee_pct,
        slippage_pct=slippage_pct,
        mode=mode,
    )

    # Write result as JSON to stdout
    print(json.dumps(result))

if __name__ == "__main__":
    main()
'''


class BacktestRunner:
    """
    Runs backtests in isolated subprocesses.

    The candidate strategy code is NEVER imported into the orchestrator.
    Instead, a child process loads and evaluates the strategy, returning
    metrics via JSON on stdout.
    """

    def __init__(self, config):
        self.config = config
        self._script_path: Optional[Path] = None

    def run_fast(self, strategy_path: Path) -> BacktestMetrics:
        """
        Quick screening run. Single symbol, no fees, last 90 days.
        """
        log.info("Running FAST backtest for %s", strategy_path)
        t0 = time.monotonic()

        symbols = self._load_symbols(tier="tier_1_single")
        request = BacktestRequest(
            strategy_path=strategy_path,
            symbols=symbols,
            days=self.config.fast_backtest_days,
            fee_pct=0.0,
            slippage_pct=0.0,
            mode="fast",
            timeout_seconds=120,
        )

        result = self._run_isolated(request)
        metrics = self._result_to_metrics(result)

        elapsed = time.monotonic() - t0
        log.info(
            "Fast backtest done in %.1fs. Sharpe=%.3f PF=%.3f trades=%d",
            elapsed,
            metrics.sharpe,
            metrics.profit_factor,
            metrics.num_trades,
        )
        return metrics

    def run_robust(self, strategy_path: Path) -> BacktestMetrics:
        """
        Full robustness run. Multi-symbol, fees, slippage, 2 years.
        Also runs a slippage stress variant.
        """
        log.info("Running ROBUST backtest for %s", strategy_path)
        t0 = time.monotonic()

        symbols = self._load_symbols(tier="all")
        request = BacktestRequest(
            strategy_path=strategy_path,
            symbols=symbols,
            days=self.config.robustness_backtest_days,
            fee_pct=0.001,
            slippage_pct=0.0005,
            mode="robust",
            timeout_seconds=600,
        )
        result = self._run_isolated(request)
        metrics = self._result_to_metrics(result)

        # Slippage stress at 2x
        stress_request = BacktestRequest(
            strategy_path=strategy_path,
            symbols=symbols,
            days=self.config.robustness_backtest_days,
            fee_pct=0.001,
            slippage_pct=0.001,
            mode="robust",
            timeout_seconds=600,
        )
        stress_result = self._run_isolated(stress_request)
        stress_metrics = self._result_to_metrics(stress_result)
        metrics.slippage_stress_sharpe = stress_metrics.sharpe

        elapsed = time.monotonic() - t0
        log.info(
            "Robust backtest done in %.1fs. Sharpe=%.3f PF=%.3f "
            "DD=%.1f%% trades=%d stress_sharpe=%.3f",
            elapsed,
            metrics.sharpe,
            metrics.profit_factor,
            metrics.max_drawdown_pct * 100,
            metrics.num_trades,
            metrics.slippage_stress_sharpe,
        )
        return metrics

    # ── Subprocess isolation ──────────────────────────────────────────────────

    def _run_isolated(self, request: BacktestRequest) -> BacktestResult:
        """
        Run backtest in isolated subprocess. Never imports candidate code
        into the orchestrator process.
        """
        script_path = self._ensure_script()
        request_json = json.dumps(
            {
                "strategy_path": str(request.strategy_path),
                "symbols": request.symbols,
                "days": request.days,
                "fee_pct": request.fee_pct,
                "slippage_pct": request.slippage_pct,
                "mode": request.mode,
            }
        )

        try:
            proc = subprocess.run(
                [sys.executable, str(script_path), request_json],
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                cwd=str(self.config.research_root),
            )
        except subprocess.TimeoutExpired:
            log.error(
                "Backtest subprocess timed out after %ds",
                request.timeout_seconds,
            )
            return BacktestResult(error="Subprocess timeout")

        if proc.returncode != 0:
            log.error(
                "Backtest subprocess failed (rc=%d): %s",
                proc.returncode,
                proc.stderr[:500],
            )
            return BacktestResult(error=f"Subprocess exit {proc.returncode}")

        try:
            data = json.loads(proc.stdout)
            return BacktestResult(**data)
        except (json.JSONDecodeError, TypeError) as e:
            log.error("Failed to parse backtest result: %s", e)
            return BacktestResult(error=f"Result parse error: {e}")

    def _ensure_script(self) -> Path:
        """Write the subprocess execution script to a temp file (cached)."""
        if self._script_path is not None and self._script_path.exists():
            return self._script_path
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, prefix="bt_runner_"
        )
        tmp.write(_SUBPROCESS_SCRIPT)
        tmp.close()
        self._script_path = Path(tmp.name)
        return self._script_path

    # ── Result parsing ────────────────────────────────────────────────────────

    def _result_to_metrics(self, result: BacktestResult) -> BacktestMetrics:
        """Convert subprocess BacktestResult into BacktestMetrics."""
        if not result.ok:
            log.warning("Backtest result not OK: %s", result.error)
            return BacktestMetrics()

        try:
            import numpy as np
            import pandas as pd
        except ImportError:
            log.error("numpy/pandas not available for metric computation")
            return BacktestMetrics()

        # Parse trades
        try:
            trades = pd.DataFrame(json.loads(result.trades_json))  # type: ignore[arg-type]
        except Exception:
            return BacktestMetrics()

        if trades.empty:
            return BacktestMetrics()

        returns = trades["return_pct"].values
        num_trades = len(trades)
        net_expectancy = float(np.mean(returns))
        median_trade = float(np.median(returns))

        gross_profit = float(returns[returns > 0].sum()) if any(returns > 0) else 0.0
        gross_loss = abs(float(returns[returns < 0].sum())) if any(returns < 0) else 1e-9
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

        # Top 5 trades PnL concentration
        sorted_returns = np.sort(returns)[::-1]
        total_positive_pnl = sorted_returns[sorted_returns > 0].sum()
        top_5_pnl = sorted_returns[:5].sum() if len(sorted_returns) >= 5 else sorted_returns.sum()
        pnl_top_5_pct = (
            float(top_5_pnl / total_positive_pnl)
            if total_positive_pnl > 0
            else 0.0
        )

        # Fee drag
        fee_drag = (
            float(result.fee_total / result.gross_profit)
            if result.gross_profit > 0
            else 0.0
        )

        # Median hold time
        median_hold_min = 0.0
        if "hold_minutes" in trades.columns:
            median_hold_min = float(trades["hold_minutes"].median())

        # Daily PnL for Sharpe / drawdown
        try:
            daily_pnl = pd.Series(
                json.loads(result.daily_pnl_json),  # type: ignore[arg-type]
                dtype=float,
            )
        except Exception:
            daily_pnl = pd.Series(dtype=float)

        if len(daily_pnl) > 1:
            mean_d = daily_pnl.mean()
            std_d = daily_pnl.std()
            sharpe = float(mean_d / std_d * (252**0.5)) if std_d > 0 else 0.0
            neg = daily_pnl[daily_pnl < 0]
            sortino_std = float(neg.std()) if len(neg) > 1 else std_d
            sortino = (
                float(mean_d / sortino_std * (252**0.5))
                if sortino_std > 0
                else 0.0
            )

            cumulative = (1 + daily_pnl).cumprod()
            rolling_max = cumulative.cummax()
            drawdown_series = (cumulative - rolling_max) / rolling_max
            max_drawdown = float(abs(drawdown_series.min()))

            total_pnl = daily_pnl.sum()
            top_day_pct = (
                float(daily_pnl.max() / total_pnl) if total_pnl > 0 else 0.0
            )
        else:
            sharpe = sortino = max_drawdown = top_day_pct = 0.0

        # Per-symbol Sharpe dispersion
        per_symbol_sharpe_std = 0.0
        if result.per_symbol_sharpe_json:
            try:
                per_sym = json.loads(result.per_symbol_sharpe_json)
                if len(per_sym) > 1:
                    per_symbol_sharpe_std = float(np.std(list(per_sym.values())))
            except Exception:
                pass

        # Regime metrics
        regime_bull = regime_bear = regime_sideways = 0.0
        if result.regime_metrics_json:
            try:
                regime = json.loads(result.regime_metrics_json)
                regime_bull = float(regime.get("bull_sharpe", 0.0))
                regime_bear = float(regime.get("bear_sharpe", 0.0))
                regime_sideways = float(regime.get("sideways_sharpe", 0.0))
            except Exception:
                pass

        return BacktestMetrics(
            sharpe=sharpe,
            sortino=sortino,
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown,
            net_expectancy=net_expectancy,
            median_trade_return=median_trade,
            num_trades=num_trades,
            total_return_pct=float(returns.sum()),
            top_day_pnl_pct=top_day_pct,
            pnl_top_5_trades_pct=pnl_top_5_pct,
            fee_drag_pct=fee_drag,
            slippage_stress_sharpe=0.0,  # filled by caller for stress run
            per_symbol_sharpe_std=per_symbol_sharpe_std,
            median_hold_minutes=median_hold_min,
            symbols_traded=result.num_symbols,
            regime_bull_sharpe=regime_bull,
            regime_bear_sharpe=regime_bear,
            regime_sideways_sharpe=regime_sideways,
            complexity_score=0.0,  # filled by loop from ComplexityReport
        )

    # ── Symbol loading ────────────────────────────────────────────────────────

    def _load_symbols(self, tier: str = "all") -> list[str]:
        """Load symbol universe from config."""
        config_path = self.config.research_root / "configs" / "symbols.yaml"
        if config_path.exists():
            import yaml

            with open(config_path) as f:
                data = yaml.safe_load(f)
            universe = data.get("universe", {})
            if tier == "tier_1_single":
                return universe.get("tier_1", ["BTC/USDT"])[:1]
            symbols = universe.get("tier_1", []) + universe.get("tier_2", [])
            return symbols or ["BTC/USDT"]
        return ["BTC/USDT"]
