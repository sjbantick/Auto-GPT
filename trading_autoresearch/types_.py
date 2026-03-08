"""
Shared dataclasses for the trading autoresearch framework.

All modules import types from here to avoid circular dependencies.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


# ── Candidate lifecycle ───────────────────────────────────────────────────────


class CandidateStatus(str, Enum):
    PENDING = "pending"
    REJECTED = "rejected"
    PAPER_CANDIDATE = "paper_candidate"
    PAPER_APPROVED = "paper_approved"
    LIVE_PROBATION = "live_probation"
    APPROVED = "approved"


# ── Backtest metrics ─────────────────────────────────────────────────────────


@dataclass
class BacktestMetrics:
    """Flat metrics produced by backtest_runner for one evaluation."""

    sharpe: float = 0.0
    sortino: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0  # Positive value, e.g. 0.15 = 15%
    net_expectancy: float = 0.0  # Mean return per trade
    median_trade_return: float = 0.0
    num_trades: int = 0
    total_return_pct: float = 0.0

    # ── Crypto-specific / expanded ────────────────────────────────────────
    top_day_pnl_pct: float = 0.0  # Fraction of total PnL from best day
    pnl_top_5_trades_pct: float = 0.0  # Fraction of PnL from top 5 trades
    fee_drag_pct: float = 0.0  # Total fees / gross profit
    slippage_stress_sharpe: float = 0.0  # Sharpe under 2x slippage
    per_symbol_sharpe_std: float = 0.0  # Std dev of per-symbol Sharpes
    median_hold_minutes: float = 0.0  # Median holding duration
    symbols_traded: int = 1

    # ── Regime slice performance ──────────────────────────────────────────
    regime_bull_sharpe: float = 0.0
    regime_bear_sharpe: float = 0.0
    regime_sideways_sharpe: float = 0.0

    # ── Complexity ────────────────────────────────────────────────────────
    complexity_score: float = 0.0


@dataclass
class WalkForwardMetrics:
    """Summary of rolling out-of-sample evaluation."""

    mean_oos_sharpe: float = 0.0
    std_oos_sharpe: float = 0.0
    pct_positive_windows: float = 0.0  # Fraction with Sharpe > 0
    num_windows: int = 0
    per_window_sharpe: list[float] = field(default_factory=list)


# ── Complexity score ──────────────────────────────────────────────────────────


@dataclass
class ComplexityReport:
    """Richer complexity measure than raw LOC."""

    lines_changed: int = 0
    new_parameters: int = 0
    branch_count_delta: int = 0
    indicator_count_delta: int = 0
    feature_count_delta: int = 0
    cyclomatic_approx: int = 0  # Sum of if/for/while/except/and/or nodes

    @property
    def score(self) -> float:
        """Weighted composite complexity score."""
        return (
            self.lines_changed * 0.01
            + self.new_parameters * 0.15
            + self.branch_count_delta * 0.10
            + self.indicator_count_delta * 0.20
            + self.feature_count_delta * 0.15
            + self.cyclomatic_approx * 0.05
        )


# ── Scorecard result ──────────────────────────────────────────────────────────


@dataclass
class ScorecardResult:
    accepted: bool
    rejection_reasons: list[str] = field(default_factory=list)
    metric_deltas: dict[str, float] = field(default_factory=dict)
    scorecard_version: str = "2.0"

    def summary(self) -> str:
        if self.accepted:
            return "ACCEPTED"
        return "REJECTED: " + " | ".join(self.rejection_reasons)


# ── Scope validation ─────────────────────────────────────────────────────────


@dataclass
class ScopeViolation:
    path: str
    reason: str


@dataclass
class ScopeReport:
    valid: bool
    violations: list[ScopeViolation] = field(default_factory=list)
    patch_line_count: int = 0
    new_files_added: int = 0
    changed_files: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.valid:
            return "OK"
        return "; ".join(f"{v.path}: {v.reason}" for v in self.violations)


# ── Static / unit check result ────────────────────────────────────────────────


@dataclass
class StaticCheckReport:
    passed: bool
    ruff_ok: bool = False
    mypy_ok: bool = False
    pytest_ok: bool = False
    details: str = ""

    @property
    def summary(self) -> str:
        if self.passed:
            return "OK"
        parts = []
        if not self.ruff_ok:
            parts.append("ruff failed")
        if not self.mypy_ok:
            parts.append("mypy failed")
        if not self.pytest_ok:
            parts.append("pytest failed")
        return "; ".join(parts) + f" — {self.details}"


# ── Leakage check result ─────────────────────────────────────────────────────


@dataclass
class LeakageWarning:
    file: str
    line: int
    pattern: str
    description: str


@dataclass
class LeakageReport:
    passed: bool
    warnings: list[LeakageWarning] = field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.passed:
            return "OK"
        return "; ".join(
            f"{w.file}:{w.line} {w.description}" for w in self.warnings
        )


# ── Backtest adapter types ────────────────────────────────────────────────────


@dataclass
class BacktestRequest:
    strategy_path: Path
    symbols: list[str]
    days: int
    fee_pct: float
    slippage_pct: float
    mode: str  # "fast" or "robust"
    timeout_seconds: int = 300


@dataclass
class BacktestResult:
    """Raw result from the backtest adapter."""

    trades_json: Optional[str] = None  # JSON-serialized trades
    daily_pnl_json: Optional[str] = None  # JSON-serialized daily PnL
    per_symbol_sharpe_json: Optional[str] = None
    num_symbols: int = 1
    strategy_path: Optional[str] = None
    fee_total: float = 0.0
    gross_profit: float = 0.0
    error: Optional[str] = None
    regime_metrics_json: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.trades_json is not None


# ── Iteration result ──────────────────────────────────────────────────────────


@dataclass
class IterationResult:
    run_id: str
    hypothesis: str
    patch_path: Optional[Path]
    baseline_run_id: Optional[str] = None
    parent_commit: Optional[str] = None
    candidate_commit: Optional[str] = None
    strategy_fingerprint: Optional[str] = None
    search_space_version: Optional[str] = None

    scope_valid: bool = False
    static_checks_passed: bool = False
    leakage_checks_passed: bool = False
    fast_bt_passed: bool = False
    robustness_passed: bool = False
    walkforward_passed: bool = False

    scorecard_result: Optional[ScorecardResult] = None
    complexity_report: Optional[ComplexityReport] = None
    status: CandidateStatus = CandidateStatus.PENDING
    rejection_reason: Optional[str] = None
    promoted_to: Optional[str] = None
    artifacts: dict[str, Any] = field(default_factory=dict)


# ── Promotion gate results ────────────────────────────────────────────────────


@dataclass
class PaperStageReport:
    num_trades: int = 0
    fee_adjusted_pf: float = 0.0
    worst_symbol_drawdown: float = 0.0
    infra_exceptions: int = 0
    duration_days: int = 0
    latency_adjusted_sharpe: float = 0.0


@dataclass
class ProbationReport:
    duration_days: int = 0
    realized_pnl: float = 0.0
    max_drawdown_pct: float = 0.0
    order_reject_rate: float = 0.0
    mean_slippage_bps: float = 0.0
    infra_exceptions: int = 0
    max_loss_breached: bool = False
    drawdown_breached: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────


def fingerprint_strategy(strategy_path: Path) -> str:
    """SHA-256 fingerprint of all Python files under strategy_path."""
    h = hashlib.sha256()
    if strategy_path.is_dir():
        for f in sorted(strategy_path.rglob("*.py")):
            h.update(f.read_bytes())
    elif strategy_path.is_file():
        h.update(strategy_path.read_bytes())
    return h.hexdigest()[:16]
