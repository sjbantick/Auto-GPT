"""
Full lineage logger for every research iteration.

Writes a structured JSON record per run plus a human-readable
markdown summary. Never modifies previous run records (append-only).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from types_ import IterationResult

log = logging.getLogger(__name__)


class ExperimentLogger:
    def __init__(self, runs_dir: Path):
        self.runs_dir = runs_dir
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def write(self, result: IterationResult) -> Path:
        """Write full experiment record. Returns path to JSON artifact."""
        run_dir = self.runs_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        record = self._build_record(result)

        json_path = run_dir / "experiment.json"
        json_path.write_text(json.dumps(record, indent=2, default=str))

        md_path = run_dir / "summary.md"
        md_path.write_text(self._build_markdown(record))

        # Copy patch artifact
        if result.patch_path and Path(result.patch_path).exists():
            (run_dir / "candidate.patch").write_bytes(
                Path(result.patch_path).read_bytes()
            )

        log.info("Experiment log written to %s", run_dir)
        return json_path

    def _build_record(self, result: IterationResult) -> dict:
        sc = result.scorecard_result
        return {
            "schema_version": "2.0",
            "run_id": result.run_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "hypothesis": result.hypothesis,
            "status": result.status.value,
            "promoted_to": result.promoted_to,
            "rejection_reason": result.rejection_reason,
            # Lineage
            "lineage": {
                "baseline_run_id": result.baseline_run_id,
                "parent_commit": result.parent_commit,
                "candidate_commit": result.candidate_commit,
                "strategy_fingerprint": result.strategy_fingerprint,
                "search_space_version": result.search_space_version,
                "scorecard_version": sc.scorecard_version if sc else None,
            },
            # Gates
            "gates": {
                "scope_valid": result.scope_valid,
                "static_checks_passed": result.static_checks_passed,
                "leakage_checks_passed": result.leakage_checks_passed,
                "fast_bt_passed": result.fast_bt_passed,
                "robustness_passed": result.robustness_passed,
                "walkforward_passed": result.walkforward_passed,
            },
            # Scorecard
            "scorecard": {
                "accepted": sc.accepted if sc else None,
                "rejection_reasons": sc.rejection_reasons if sc else [],
                "metric_deltas": sc.metric_deltas if sc else {},
            }
            if sc is not None
            else None,
            # Complexity
            "complexity": (
                asdict(result.complexity_report)
                if result.complexity_report
                else None
            ),
            # Raw metrics
            "raw_metrics": {
                k: self._safe_serialize(v)
                for k, v in result.artifacts.items()
            },
        }

    @staticmethod
    def _safe_serialize(obj: Any) -> Any:
        try:
            return asdict(obj)
        except (TypeError, AttributeError):
            return str(obj)

    def _build_markdown(self, record: dict) -> str:
        gates = record.get("gates") or {}
        sc = record.get("scorecard") or {}
        deltas = sc.get("metric_deltas") or {}
        lineage = record.get("lineage") or {}

        def icon(v: Optional[bool]) -> str:
            if v is True:
                return "PASS"
            if v is False:
                return "FAIL"
            return "---"

        lines = [
            f"# Experiment: {record['run_id']}",
            f"**Status**: `{record['status']}`  ",
            f"**Timestamp**: {record['timestamp_utc']}  ",
            "",
            "## Hypothesis",
            f"> {record['hypothesis']}",
            "",
            "## Lineage",
            f"| Field | Value |",
            f"|---|---|",
        ]
        for k, v in lineage.items():
            lines.append(f"| {k} | `{v}` |")

        lines += [
            "",
            "## Gate Results",
            "| Gate | Result |",
            "|---|---|",
        ]
        for k, v in gates.items():
            lines.append(f"| {k} | {icon(v)} |")

        if deltas:
            lines += [
                "",
                "## Metric Deltas vs Baseline",
                "| Metric | Value |",
                "|---|---|",
            ]
            for k, v in deltas.items():
                if isinstance(v, float):
                    sign = "+" if v >= 0 else ""
                    lines.append(f"| {k} | {sign}{v:.4f} |")
                else:
                    lines.append(f"| {k} | {v} |")

        if record.get("complexity"):
            cx = record["complexity"]
            lines += [
                "",
                "## Complexity",
                "| Measure | Value |",
                "|---|---|",
            ]
            for k, v in cx.items():
                lines.append(f"| {k} | {v} |")

        if record.get("rejection_reason"):
            lines += [
                "",
                "## Rejection Reason",
                "```",
                record["rejection_reason"],
                "```",
            ]

        if record.get("promoted_to"):
            lines += [
                "",
                "## Promotion",
                f"Promoted to: **{record['promoted_to']}**",
                "",
                "> Human review required for next stage.",
            ]

        return "\n".join(lines)
