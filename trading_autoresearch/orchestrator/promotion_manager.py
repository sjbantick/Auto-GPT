"""
Promotion state machine with explicit gates at every stage.

Fixes vs v1:
  - Defines precise criteria for each promotion transition
  - paper_candidate -> paper_approved: requires PaperStageReport checks
  - paper_approved -> live_probation: requires duration + latency checks
  - live_probation -> approved: requires ProbationReport checks
  - Auto-demotion triggers are explicit and logged
  - Every promotion past paper_candidate requires human_approved=True
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from orchestrator.candidate_registry import CandidateRegistry
from types_ import CandidateStatus, PaperStageReport, ProbationReport

log = logging.getLogger(__name__)

# ── Stage ordering ────────────────────────────────────────────────────────────

PROMOTION_ORDER = [
    CandidateStatus.PENDING,
    CandidateStatus.PAPER_CANDIDATE,
    CandidateStatus.PAPER_APPROVED,
    CandidateStatus.LIVE_PROBATION,
    CandidateStatus.APPROVED,
]

# These stages require explicit human --approve
HUMAN_GATE_STAGES = {
    CandidateStatus.PAPER_APPROVED,
    CandidateStatus.LIVE_PROBATION,
    CandidateStatus.APPROVED,
}


# ── Gate configs ──────────────────────────────────────────────────────────────


@dataclass
class PaperGateConfig:
    """Requirements for paper_candidate -> paper_approved."""

    min_paper_trades: int = 100
    min_fee_adjusted_pf: float = 1.05
    max_worst_symbol_drawdown: float = 0.15  # 15%
    max_infra_exceptions: int = 5
    min_duration_days: int = 14


@dataclass
class ProbationEntryConfig:
    """Requirements for paper_approved -> live_probation."""

    min_paper_duration_days: int = 30
    min_latency_adjusted_sharpe: float = 0.0
    max_position_size_usd: float = 100
    max_loss_usd: float = 50
    probation_duration_days: int = 14


@dataclass
class ApprovalConfig:
    """Requirements for live_probation -> approved."""

    min_probation_duration_days: int = 14
    max_drawdown_pct: float = 0.20
    max_order_reject_rate: float = 0.05  # 5%
    max_slippage_bps: float = 15.0
    max_infra_exceptions: int = 3
    max_loss_usd: float = 50


# ── Auto-demotion triggers ────────────────────────────────────────────────────


@dataclass
class DemotionTriggers:
    """Conditions that auto-demote from live_probation."""

    max_loss_usd: float = 50
    max_drawdown_pct: float = 0.20
    max_infra_exceptions: int = 10
    max_order_reject_rate: float = 0.10
    max_slippage_bps: float = 25.0


# ── Manager ───────────────────────────────────────────────────────────────────


class PromotionManager:
    def __init__(
        self,
        registry: CandidateRegistry,
        paper_gate: Optional[PaperGateConfig] = None,
        probation_entry: Optional[ProbationEntryConfig] = None,
        approval: Optional[ApprovalConfig] = None,
        demotion: Optional[DemotionTriggers] = None,
    ):
        self.registry = registry
        self.paper_gate = paper_gate or PaperGateConfig()
        self.probation_entry = probation_entry or ProbationEntryConfig()
        self.approval = approval or ApprovalConfig()
        self.demotion = demotion or DemotionTriggers()

    # ── Promotion ─────────────────────────────────────────────────────────

    def promote(
        self,
        run_id: str,
        human_approved: bool = False,
        paper_report: Optional[PaperStageReport] = None,
        probation_report: Optional[ProbationReport] = None,
    ) -> tuple[CandidateStatus, str]:
        """
        Attempt to promote a candidate to the next stage.

        Returns (new_status, message).
        Raises PermissionError if human approval required but not given.
        """
        candidate = self.registry.get(run_id)
        if candidate is None:
            raise ValueError(f"Unknown run_id: {run_id}")

        current = CandidateStatus(candidate["status"])
        next_stage = self._next_stage(current)

        if next_stage is None:
            return current, f"Already at terminal stage: {current.value}"

        if current == CandidateStatus.REJECTED:
            return current, "Cannot promote a rejected candidate"

        # All stages past paper_candidate require human approval
        if next_stage in HUMAN_GATE_STAGES and not human_approved:
            raise PermissionError(
                f"Promoting to {next_stage.value} requires --approve flag.\n"
                f"Run: autoresearch promote --run-id {run_id} --approve"
            )

        # ── Gate checks ───────────────────────────────────────────────

        if next_stage == CandidateStatus.PAPER_APPROVED:
            ok, reason = self._check_paper_gate(paper_report)
            if not ok:
                return current, f"Paper gate failed: {reason}"

        elif next_stage == CandidateStatus.LIVE_PROBATION:
            ok, reason = self._check_probation_entry(paper_report)
            if not ok:
                return current, f"Probation entry gate failed: {reason}"
            # Attach probation config
            self.registry.attach_probation_config(
                run_id,
                {
                    "max_position_size_usd": self.probation_entry.max_position_size_usd,
                    "max_loss_usd": self.probation_entry.max_loss_usd,
                    "duration_days": self.probation_entry.probation_duration_days,
                },
            )
            log.warning(
                "=== LIVE PROBATION ACTIVATED for %s ===\n"
                "  max_position: $%.0f\n"
                "  max_loss: $%.0f\n"
                "  duration: %d days\n"
                "  Auto-demotion on breach.",
                run_id,
                self.probation_entry.max_position_size_usd,
                self.probation_entry.max_loss_usd,
                self.probation_entry.probation_duration_days,
            )

        elif next_stage == CandidateStatus.APPROVED:
            ok, reason = self._check_approval(probation_report)
            if not ok:
                return current, f"Approval gate failed: {reason}"

        # ── Execute promotion ─────────────────────────────────────────
        self.registry.update_status(
            run_id,
            next_stage,
            reason=f"Promoted from {current.value}",
        )
        msg = f"Promoted {run_id}: {current.value} -> {next_stage.value}"
        log.info(msg)
        return next_stage, msg

    # ── Auto-demotion ─────────────────────────────────────────────────────

    def check_demotion(
        self, run_id: str, report: ProbationReport
    ) -> tuple[bool, str]:
        """
        Check if a live-probation candidate should be auto-demoted.
        Returns (demoted, reason).
        """
        reasons = []

        if report.max_loss_breached:
            reasons.append("Max loss breached")

        if report.max_drawdown_pct > self.demotion.max_drawdown_pct:
            reasons.append(
                f"Drawdown {report.max_drawdown_pct:.1%} > "
                f"{self.demotion.max_drawdown_pct:.1%}"
            )

        if report.infra_exceptions > self.demotion.max_infra_exceptions:
            reasons.append(
                f"Infra exceptions {report.infra_exceptions} > "
                f"{self.demotion.max_infra_exceptions}"
            )

        if report.order_reject_rate > self.demotion.max_order_reject_rate:
            reasons.append(
                f"Order reject rate {report.order_reject_rate:.1%} > "
                f"{self.demotion.max_order_reject_rate:.1%}"
            )

        if report.mean_slippage_bps > self.demotion.max_slippage_bps:
            reasons.append(
                f"Slippage {report.mean_slippage_bps:.1f}bps > "
                f"{self.demotion.max_slippage_bps:.1f}bps"
            )

        if report.drawdown_breached:
            reasons.append("Hard drawdown limit breached")

        if reasons:
            reason_str = "; ".join(reasons)
            self.registry.update_status(
                run_id,
                CandidateStatus.REJECTED,
                reason=f"Auto-demoted: {reason_str}",
            )
            self.registry.attach_note(
                run_id, f"Auto-demoted from live_probation: {reason_str}"
            )
            log.warning("DEMOTED %s: %s", run_id, reason_str)
            return True, reason_str

        return False, ""

    # ── Gate checks ───────────────────────────────────────────────────────

    def _check_paper_gate(
        self, report: Optional[PaperStageReport]
    ) -> tuple[bool, str]:
        """paper_candidate -> paper_approved gate."""
        if report is None:
            return False, "No PaperStageReport provided"

        cfg = self.paper_gate
        reasons = []

        if report.num_trades < cfg.min_paper_trades:
            reasons.append(
                f"Paper trades {report.num_trades} < {cfg.min_paper_trades}"
            )
        if report.fee_adjusted_pf < cfg.min_fee_adjusted_pf:
            reasons.append(
                f"Fee-adjusted PF {report.fee_adjusted_pf:.3f} < "
                f"{cfg.min_fee_adjusted_pf}"
            )
        if report.worst_symbol_drawdown > cfg.max_worst_symbol_drawdown:
            reasons.append(
                f"Worst symbol DD {report.worst_symbol_drawdown:.1%} > "
                f"{cfg.max_worst_symbol_drawdown:.1%}"
            )
        if report.infra_exceptions > cfg.max_infra_exceptions:
            reasons.append(
                f"Infra exceptions {report.infra_exceptions} > "
                f"{cfg.max_infra_exceptions}"
            )
        if report.duration_days < cfg.min_duration_days:
            reasons.append(
                f"Paper duration {report.duration_days}d < "
                f"{cfg.min_duration_days}d"
            )

        if reasons:
            return False, "; ".join(reasons)
        return True, ""

    def _check_probation_entry(
        self, report: Optional[PaperStageReport]
    ) -> tuple[bool, str]:
        """paper_approved -> live_probation gate."""
        if report is None:
            return False, "No PaperStageReport provided"

        cfg = self.probation_entry
        reasons = []

        if report.duration_days < cfg.min_paper_duration_days:
            reasons.append(
                f"Paper duration {report.duration_days}d < "
                f"{cfg.min_paper_duration_days}d"
            )
        if report.latency_adjusted_sharpe < cfg.min_latency_adjusted_sharpe:
            reasons.append(
                f"Latency-adjusted Sharpe {report.latency_adjusted_sharpe:.3f} < "
                f"{cfg.min_latency_adjusted_sharpe}"
            )

        if reasons:
            return False, "; ".join(reasons)
        return True, ""

    def _check_approval(
        self, report: Optional[ProbationReport]
    ) -> tuple[bool, str]:
        """live_probation -> approved gate."""
        if report is None:
            return False, "No ProbationReport provided"

        cfg = self.approval
        reasons = []

        if report.duration_days < cfg.min_probation_duration_days:
            reasons.append(
                f"Probation {report.duration_days}d < "
                f"{cfg.min_probation_duration_days}d"
            )
        if report.max_drawdown_pct > cfg.max_drawdown_pct:
            reasons.append(
                f"DD {report.max_drawdown_pct:.1%} > {cfg.max_drawdown_pct:.1%}"
            )
        if report.order_reject_rate > cfg.max_order_reject_rate:
            reasons.append(
                f"Order reject rate {report.order_reject_rate:.1%} > "
                f"{cfg.max_order_reject_rate:.1%}"
            )
        if report.mean_slippage_bps > cfg.max_slippage_bps:
            reasons.append(
                f"Slippage {report.mean_slippage_bps:.1f}bps > "
                f"{cfg.max_slippage_bps:.1f}bps"
            )
        if report.infra_exceptions > cfg.max_infra_exceptions:
            reasons.append(
                f"Infra exceptions {report.infra_exceptions} > "
                f"{cfg.max_infra_exceptions}"
            )
        if report.max_loss_breached:
            reasons.append("Max loss was breached during probation")

        if reasons:
            return False, "; ".join(reasons)
        return True, ""

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _next_stage(current: CandidateStatus) -> Optional[CandidateStatus]:
        try:
            idx = PROMOTION_ORDER.index(current)
            return (
                PROMOTION_ORDER[idx + 1]
                if idx + 1 < len(PROMOTION_ORDER)
                else None
            )
        except ValueError:
            return None
