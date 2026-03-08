"""
Main autoresearch loop.

Runs one hypothesis iteration at a time through the full evaluation ladder.
Never auto-deploys. Requires explicit human promotion for stages beyond
paper_candidate.

Fixes vs v1:
  - OOS comparison: candidate walk-forward OOS vs BASELINE walk-forward OOS
    (not candidate OOS vs baseline in-sample Sharpe)
  - Runs walk-forward on BOTH candidate AND baseline, then compares OOS-to-OOS
  - Leakage/lookahead check added as Stage 2 before any backtest
  - Fast screen uses multi-criteria rejection (not just Sharpe > 0)
  - Candidate code evaluated in subprocess isolation
  - Complexity measured via richer ComplexityReport
  - Full lineage: baseline_run_id, parent/candidate commits, fingerprint
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from evaluator.backtest_runner import BacktestRunner
from evaluator.leakage_checks import LeakageChecker
from evaluator.scorecard import Scorecard, ScorecardConfig
from evaluator.unit_runner import UnitRunner
from evaluator.walkforward_runner import WalkForwardRunner
from orchestrator.candidate_registry import CandidateRegistry
from orchestrator.patch_manager import PatchManager
from reports.experiment_log import ExperimentLogger
from sandbox.constraints import ScopeValidator
from sandbox.git_sandbox import GitSandbox
from types_ import (
    CandidateStatus,
    IterationResult,
    WalkForwardMetrics,
    fingerprint_strategy,
)

log = logging.getLogger(__name__)


@dataclass
class LoopConfig:
    baseline_strategy_path: Path
    research_root: Path
    max_iterations: int = 10
    fast_backtest_days: int = 90
    robustness_backtest_days: int = 730
    min_trades_absolute: int = 30
    wf_train_days: int = 90
    wf_test_days: int = 30
    wf_n_windows: int = 8
    dry_run: bool = False


class ResearchLoop:
    """
    Orchestrates one bounded hypothesis iteration.

    The loop never touches execution/, brokers/, auth/, or any
    forbidden path. Promotion beyond paper_candidate requires
    explicit human invocation of PromotionManager.
    """

    def __init__(
        self,
        config: LoopConfig,
        agent_callable: Optional[Callable] = None,
    ):
        self.config = config
        self.agent = agent_callable
        self.scope_validator = ScopeValidator(config.research_root)
        self.patch_manager = PatchManager(config.baseline_strategy_path)
        self.registry = CandidateRegistry(
            config.research_root / ".candidates.db"
        )
        self.logger = ExperimentLogger(config.research_root / "reports" / "runs")
        self.backtest_runner = BacktestRunner(config)
        self.walkforward_runner = WalkForwardRunner(config)
        self.scorecard = Scorecard()
        self.unit_runner = UnitRunner(config.research_root)
        self.leakage_checker = LeakageChecker()

        # Load search space version for lineage
        self._search_space_version = self._hash_config(
            config.research_root / "configs" / "search_space.yaml"
        )

    def run_iteration(self, hypothesis: Optional[str] = None) -> IterationResult:
        run_id = (
            f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:6]}"
        )
        log.info("=== Research Iteration %s ===", run_id)

        # Get the current baseline run_id for lineage
        baseline_record = self.registry.get_approved_baseline()
        baseline_run_id = baseline_record["run_id"] if baseline_record else None

        # ── Stage 0: Get hypothesis ───────────────────────────────────────
        if hypothesis is None:
            if self.agent is None:
                raise ValueError(
                    "No agent callable and no hypothesis provided."
                )
            hypothesis = self.agent("propose_hypothesis")

        log.info("Hypothesis: %s", hypothesis)

        # ── Create sandbox ────────────────────────────────────────────────
        with GitSandbox(self.config.research_root, run_id) as sandbox:
            parent_commit = sandbox.get_commit_sha()

            result = IterationResult(
                run_id=run_id,
                hypothesis=hypothesis,
                patch_path=None,
                baseline_run_id=baseline_run_id,
                parent_commit=parent_commit,
                search_space_version=self._search_space_version,
            )

            # ── Stage 1: Generate and apply patch ─────────────────────────
            patch_path = self.patch_manager.apply_hypothesis(
                hypothesis, sandbox.worktree_path, self.agent
            )
            result.patch_path = patch_path

            if patch_path is None:
                result.status = CandidateStatus.REJECTED
                result.rejection_reason = "Failed to generate or apply patch"
                self._finalize(result, sandbox)
                return result

            # Record candidate commit + fingerprint
            candidate_commit = sandbox.commit_candidate(
                f"autoresearch: {hypothesis[:80]}"
            )
            result.candidate_commit = candidate_commit
            result.strategy_fingerprint = fingerprint_strategy(
                sandbox.worktree_path / "strategies"
            )

            # ── Stage 2: Scope validation ─────────────────────────────────
            scope_ok, scope_report = self.scope_validator.validate(
                sandbox.worktree_path, patch_path
            )
            result.scope_valid = scope_ok
            result.artifacts["scope_report"] = scope_report
            if not scope_ok:
                result.status = CandidateStatus.REJECTED
                result.rejection_reason = (
                    f"Scope violation: {scope_report.summary}"
                )
                self._finalize(result, sandbox)
                return result

            # Compute complexity from patch
            patch_text = patch_path.read_text()
            complexity = self.scope_validator.compute_complexity(
                worktree_path=sandbox.worktree_path,
                baseline_path=self.config.baseline_strategy_path,
                changed_files=scope_report.changed_files,
                patch_text=patch_text,
            )
            result.complexity_report = complexity

            # ── Stage 3: Static checks ────────────────────────────────────
            static_ok, static_report = self.unit_runner.run(
                sandbox.worktree_path
            )
            result.static_checks_passed = static_ok
            result.artifacts["static_report"] = static_report
            if not static_ok:
                result.status = CandidateStatus.REJECTED
                result.rejection_reason = (
                    f"Static checks failed: {static_report.summary}"
                )
                self._finalize(result, sandbox)
                return result

            # ── Stage 4: Leakage / lookahead check ────────────────────────
            leakage_report = self.leakage_checker.check(
                sandbox.worktree_path, scope_report.changed_files
            )
            result.leakage_checks_passed = leakage_report.passed
            result.artifacts["leakage_report"] = leakage_report
            if not leakage_report.passed:
                result.status = CandidateStatus.REJECTED
                result.rejection_reason = (
                    f"Leakage check failed: {leakage_report.summary}"
                )
                self._finalize(result, sandbox)
                return result

            # ── Stage 5: Fast backtest ────────────────────────────────────
            fast_metrics = self.backtest_runner.run_fast(
                sandbox.worktree_path / "strategies"
            )
            result.artifacts["fast_metrics"] = fast_metrics

            fast_ok, fast_reason = self.scorecard.fast_screen(fast_metrics)
            result.fast_bt_passed = fast_ok
            if not fast_ok:
                result.status = CandidateStatus.REJECTED
                result.rejection_reason = fast_reason
                self._finalize(result, sandbox)
                return result

            # ── Stage 6: Robustness backtest ──────────────────────────────
            candidate_robust = self.backtest_runner.run_robust(
                sandbox.worktree_path / "strategies"
            )
            candidate_robust.complexity_score = complexity.score
            result.artifacts["robust_metrics"] = candidate_robust

            # ── Stage 7: Walk-forward on BOTH candidate AND baseline ──────
            #
            # CRITICAL FIX: We run walk-forward on the baseline too,
            # so the scorecard compares OOS-to-OOS.
            #
            candidate_wf = self.walkforward_runner.run(
                sandbox.worktree_path / "strategies"
            )
            baseline_wf = self.walkforward_runner.run(
                self.config.baseline_strategy_path
            )
            result.artifacts["walkforward_candidate"] = candidate_wf
            result.artifacts["walkforward_baseline"] = baseline_wf

            # Baseline robustness for comparison
            baseline_robust = self.backtest_runner.run_robust(
                self.config.baseline_strategy_path
            )
            result.artifacts["baseline_robust"] = baseline_robust

            # ── Stage 8: Scorecard — OOS-to-OOS comparison ────────────────
            sc_result = self.scorecard.evaluate(
                candidate=candidate_robust,
                candidate_wf=candidate_wf,
                baseline=baseline_robust,
                baseline_wf=baseline_wf,  # <-- THE FIX: baseline OOS, not IS
                complexity_report=complexity,
            )
            result.scorecard_result = sc_result

            if sc_result.accepted:
                result.status = CandidateStatus.PAPER_CANDIDATE
                result.promoted_to = "paper_candidate"
                result.robustness_passed = True
                result.walkforward_passed = True
                log.info(
                    "Candidate ACCEPTED -> paper_candidate: %s", run_id
                )
            else:
                result.status = CandidateStatus.REJECTED
                result.rejection_reason = "; ".join(
                    sc_result.rejection_reasons
                )
                log.info(
                    "Candidate REJECTED: %s", result.rejection_reason
                )

            self._finalize(result, sandbox)
            return result

    def run_n_iterations(self, n: Optional[int] = None) -> list[IterationResult]:
        n = n or self.config.max_iterations
        results = []
        for i in range(n):
            log.info("--- Iteration %d / %d ---", i + 1, n)
            try:
                r = self.run_iteration()
                results.append(r)
            except Exception:
                log.exception("Iteration %d crashed", i + 1)
        return results

    # ── Internal ──────────────────────────────────────────────────────────────

    def _finalize(self, result: IterationResult, sandbox: GitSandbox) -> None:
        self.registry.save(result)
        self.logger.write(result)
        if (
            result.status == CandidateStatus.PAPER_CANDIDATE
            and not self.config.dry_run
        ):
            sandbox.preserve()
        log.info(
            "Iteration %s complete. Status: %s",
            result.run_id,
            result.status.value,
        )

    @staticmethod
    def _hash_config(path: Path) -> str:
        if path.exists():
            return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
        return "none"
