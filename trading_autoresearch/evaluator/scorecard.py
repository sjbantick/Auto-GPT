"""
Multi-metric acceptance scorecard for crypto trading strategies.

Fixes vs v1:
  - OOS comparison: candidate walk-forward OOS vs BASELINE walk-forward OOS
    (not candidate OOS vs baseline in-sample)
  - Expanded crypto-specific metrics:
    fee_drag_pct, pnl_top_5_trades_pct, per_symbol_sharpe_dispersion,
    median_hold_minutes, regime_slice_performance
  - Stronger fast-screen logic (not just Sharpe > 0)
  - Richer complexity score from ComplexityReport

A candidate is accepted only when ALL primary metrics pass
AND all guardrail checks clear.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from types_ import (
    BacktestMetrics,
    ComplexityReport,
    ScorecardResult,
    WalkForwardMetrics,
)

log = logging.getLogger(__name__)


@dataclass
class ScorecardConfig:
    """All thresholds in one place, loadable from risk_limits.yaml."""

    # ── Absolute minimums ─────────────────────────────────────────────────
    min_trades: int = 30
    min_profit_factor: float = 1.05
    min_net_expectancy: float = 0.0
    min_oos_positive_window_pct: float = 0.50

    # ── Regression tolerances vs baseline ─────────────────────────────────
    max_drawdown_regression: float = 1.10  # candidate DD <= baseline * 1.10
    min_profit_factor_ratio: float = 0.95
    min_trade_count_ratio: float = 0.80
    min_oos_sharpe_ratio: float = 0.90  # candidate OOS vs BASELINE OOS

    # ── Concentration / robustness ────────────────────────────────────────
    max_top_day_pnl_concentration: float = 0.25
    max_top_5_trades_pnl_concentration: float = 0.40
    min_slippage_stress_ratio: float = 0.70  # stress Sharpe / base Sharpe
    max_fee_drag_pct: float = 0.50  # fees / gross profit
    max_per_symbol_sharpe_std: float = 1.5  # std dev of per-symbol Sharpes

    # ── Complexity ────────────────────────────────────────────────────────
    max_complexity_delta: float = 1.0

    # ── Regime ────────────────────────────────────────────────────────────
    min_worst_regime_sharpe: float = -0.5  # No regime catastrophically bad

    # ── Fast screen thresholds ────────────────────────────────────────────
    fast_min_trades: int = 10
    fast_min_expectancy: float = 0.0
    fast_min_profit_factor: float = 1.0
    fast_max_drawdown_pct: float = 0.30
    fast_min_sharpe: float = 0.0


class Scorecard:
    """
    Evaluates a candidate strategy against the current approved baseline.

    CRITICAL FIX: OOS comparison uses baseline WALK-FORWARD metrics,
    not baseline in-sample metrics. This prevents the false-positive
    where a candidate with mediocre OOS performance "passes" by
    comparison to an inflated baseline in-sample Sharpe.
    """

    def __init__(self, config: Optional[ScorecardConfig] = None):
        self.cfg = config or ScorecardConfig()

    # ── Fast screen (Stage 3) ─────────────────────────────────────────────────

    def fast_screen(self, metrics: BacktestMetrics) -> tuple[bool, str]:
        """
        Stronger fast-screen logic. Rejects on multiple criteria,
        not just Sharpe > 0.

        Returns (passed, reason_if_failed).
        """
        reasons = []

        if metrics.num_trades < self.cfg.fast_min_trades:
            reasons.append(
                f"trades={metrics.num_trades} < {self.cfg.fast_min_trades}"
            )

        if metrics.net_expectancy < self.cfg.fast_min_expectancy:
            reasons.append(
                f"expectancy={metrics.net_expectancy:.4f} < "
                f"{self.cfg.fast_min_expectancy}"
            )

        if metrics.profit_factor < self.cfg.fast_min_profit_factor:
            reasons.append(
                f"PF={metrics.profit_factor:.3f} < "
                f"{self.cfg.fast_min_profit_factor}"
            )

        if metrics.max_drawdown_pct > self.cfg.fast_max_drawdown_pct:
            reasons.append(
                f"DD={metrics.max_drawdown_pct:.1%} > "
                f"{self.cfg.fast_max_drawdown_pct:.1%}"
            )

        if metrics.sharpe < self.cfg.fast_min_sharpe:
            reasons.append(
                f"Sharpe={metrics.sharpe:.3f} < {self.cfg.fast_min_sharpe}"
            )

        # Fee-adjusted check: if we have fee info, net expectancy must survive
        if metrics.fee_drag_pct > 0.95:
            reasons.append(
                f"fee_drag={metrics.fee_drag_pct:.0%} — fees consume nearly all profit"
            )

        if reasons:
            msg = "Fast screen failed: " + "; ".join(reasons)
            return False, msg
        return True, ""

    # ── Full scorecard (Stage 5–6) ────────────────────────────────────────────

    def evaluate(
        self,
        candidate: BacktestMetrics,
        candidate_wf: WalkForwardMetrics,
        baseline: BacktestMetrics,
        baseline_wf: WalkForwardMetrics,
        complexity_report: Optional[ComplexityReport] = None,
    ) -> ScorecardResult:
        """
        Compare candidate vs baseline on all metrics + guardrails.

        NOTE: baseline_wf is the baseline's OOS walk-forward result,
        ensuring we compare OOS-to-OOS, not OOS-to-in-sample.
        """
        reasons: list[str] = []

        # ── Absolute guardrails ───────────────────────────────────────────

        if candidate.num_trades < self.cfg.min_trades:
            reasons.append(
                f"Trade count too low: {candidate.num_trades} < "
                f"{self.cfg.min_trades}"
            )

        if candidate.net_expectancy <= self.cfg.min_net_expectancy:
            reasons.append(
                f"Non-positive net expectancy: "
                f"{candidate.net_expectancy:.4f}"
            )

        if candidate.profit_factor < self.cfg.min_profit_factor:
            reasons.append(
                f"Profit factor below minimum: "
                f"{candidate.profit_factor:.3f} < "
                f"{self.cfg.min_profit_factor}"
            )

        if candidate_wf.pct_positive_windows < self.cfg.min_oos_positive_window_pct:
            reasons.append(
                f"Too few positive OOS windows: "
                f"{candidate_wf.pct_positive_windows:.0%} < "
                f"{self.cfg.min_oos_positive_window_pct:.0%}"
            )

        # ── Regression vs baseline ────────────────────────────────────────

        if baseline.num_trades > 0:
            trade_ratio = candidate.num_trades / baseline.num_trades
            if trade_ratio < self.cfg.min_trade_count_ratio:
                reasons.append(
                    f"Trade count regressed: {trade_ratio:.0%} of baseline "
                    f"(min {self.cfg.min_trade_count_ratio:.0%})"
                )

        if (
            baseline.max_drawdown_pct > 0
            and candidate.max_drawdown_pct
            > baseline.max_drawdown_pct * self.cfg.max_drawdown_regression
        ):
            reasons.append(
                f"Drawdown materially worse: {candidate.max_drawdown_pct:.1%} "
                f"vs baseline {baseline.max_drawdown_pct:.1%}"
            )

        if baseline.profit_factor > 0:
            pf_ratio = candidate.profit_factor / baseline.profit_factor
            if pf_ratio < self.cfg.min_profit_factor_ratio:
                reasons.append(
                    f"Profit factor regressed: ratio={pf_ratio:.3f}"
                )

        # ── OOS Sharpe: candidate OOS vs BASELINE OOS (the fix) ───────────
        if baseline_wf.mean_oos_sharpe > 0:
            oos_ratio = candidate_wf.mean_oos_sharpe / baseline_wf.mean_oos_sharpe
            if oos_ratio < self.cfg.min_oos_sharpe_ratio:
                reasons.append(
                    f"OOS Sharpe regressed vs baseline OOS: "
                    f"candidate={candidate_wf.mean_oos_sharpe:.3f} "
                    f"baseline={baseline_wf.mean_oos_sharpe:.3f} "
                    f"ratio={oos_ratio:.3f}"
                )

        # ── Concentration guardrails ──────────────────────────────────────

        if candidate.top_day_pnl_pct > self.cfg.max_top_day_pnl_concentration:
            reasons.append(
                f"PnL concentrated in single day: "
                f"{candidate.top_day_pnl_pct:.0%} > "
                f"{self.cfg.max_top_day_pnl_concentration:.0%}"
            )

        if (
            candidate.pnl_top_5_trades_pct
            > self.cfg.max_top_5_trades_pnl_concentration
        ):
            reasons.append(
                f"PnL concentrated in top 5 trades: "
                f"{candidate.pnl_top_5_trades_pct:.0%} > "
                f"{self.cfg.max_top_5_trades_pnl_concentration:.0%}"
            )

        # ── Slippage stress ───────────────────────────────────────────────
        if candidate.sharpe > 0:
            slip_ratio = candidate.slippage_stress_sharpe / candidate.sharpe
            if slip_ratio < self.cfg.min_slippage_stress_ratio:
                reasons.append(
                    f"Slippage sensitivity too high: "
                    f"stress/base={slip_ratio:.2f} "
                    f"(min {self.cfg.min_slippage_stress_ratio:.2f})"
                )

        # ── Fee drag ──────────────────────────────────────────────────────
        if candidate.fee_drag_pct > self.cfg.max_fee_drag_pct:
            reasons.append(
                f"Fee drag too high: {candidate.fee_drag_pct:.0%} "
                f"(max {self.cfg.max_fee_drag_pct:.0%})"
            )

        # ── Symbol dispersion ─────────────────────────────────────────────
        if candidate.per_symbol_sharpe_std > self.cfg.max_per_symbol_sharpe_std:
            reasons.append(
                f"Per-symbol Sharpe dispersion too high: "
                f"std={candidate.per_symbol_sharpe_std:.2f} "
                f"(max {self.cfg.max_per_symbol_sharpe_std:.2f})"
            )

        # ── Regime performance ────────────────────────────────────────────
        worst_regime = min(
            candidate.regime_bull_sharpe,
            candidate.regime_bear_sharpe,
            candidate.regime_sideways_sharpe,
        )
        if worst_regime < self.cfg.min_worst_regime_sharpe:
            reasons.append(
                f"Worst regime Sharpe too low: {worst_regime:.3f} "
                f"(min {self.cfg.min_worst_regime_sharpe:.3f})"
            )

        # ── Complexity ────────────────────────────────────────────────────
        if complexity_report is not None:
            cdelta = complexity_report.score - 0  # baseline complexity is 0 by def
            if cdelta > self.cfg.max_complexity_delta:
                reasons.append(
                    f"Complexity increase too large: +{cdelta:.2f} "
                    f"(max +{self.cfg.max_complexity_delta:.2f})"
                )

        # ── Build result ──────────────────────────────────────────────────
        deltas = {
            "sharpe_delta": candidate.sharpe - baseline.sharpe,
            "sortino_delta": candidate.sortino - baseline.sortino,
            "pf_delta": candidate.profit_factor - baseline.profit_factor,
            "drawdown_delta": candidate.max_drawdown_pct - baseline.max_drawdown_pct,
            "trades_delta": candidate.num_trades - baseline.num_trades,
            "oos_sharpe_candidate": candidate_wf.mean_oos_sharpe,
            "oos_sharpe_baseline": baseline_wf.mean_oos_sharpe,
            "oos_sharpe_std": candidate_wf.std_oos_sharpe,
            "fee_drag_pct": candidate.fee_drag_pct,
            "top_day_pnl_pct": candidate.top_day_pnl_pct,
            "pnl_top_5_trades_pct": candidate.pnl_top_5_trades_pct,
            "per_symbol_sharpe_std": candidate.per_symbol_sharpe_std,
            "median_hold_minutes": candidate.median_hold_minutes,
            "slippage_stress_sharpe": candidate.slippage_stress_sharpe,
            "complexity_score": (
                complexity_report.score if complexity_report else 0.0
            ),
        }

        accepted = len(reasons) == 0
        result = ScorecardResult(
            accepted=accepted,
            rejection_reasons=reasons,
            metric_deltas=deltas,
        )

        log.info("Scorecard: %s", result.summary())
        for k, v in deltas.items():
            log.info("  %s: %+.4f", k, v)

        return result
