"""
SQLite-backed candidate registry with full lineage tracking.

Fixes vs v1:
  - Tracks baseline_run_id, parent_commit, candidate_commit
  - Tracks strategy_fingerprint, search_space_version, scorecard_version
  - Append-only audit log table for all status transitions
  - Proper schema with indices
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from types_ import CandidateStatus, IterationResult

log = logging.getLogger(__name__)


class CandidateRegistry:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    # ── Public API ────────────────────────────────────────────────────────────

    def save(self, result: IterationResult) -> None:
        """Insert or update a candidate record with full lineage."""
        sc = result.scorecard_result
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO candidates (
                    run_id,
                    hypothesis,
                    status,
                    rejection_reason,
                    promoted_to,
                    baseline_run_id,
                    parent_commit,
                    candidate_commit,
                    strategy_fingerprint,
                    search_space_version,
                    scorecard_version,
                    metric_deltas_json,
                    complexity_json,
                    artifacts_json,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    result.hypothesis,
                    result.status.value,
                    result.rejection_reason,
                    result.promoted_to,
                    result.baseline_run_id,
                    result.parent_commit,
                    result.candidate_commit,
                    result.strategy_fingerprint,
                    result.search_space_version,
                    sc.scorecard_version if sc else None,
                    json.dumps(sc.metric_deltas if sc else {}),
                    json.dumps(
                        {
                            "lines_changed": result.complexity_report.lines_changed,
                            "new_parameters": result.complexity_report.new_parameters,
                            "branch_count_delta": result.complexity_report.branch_count_delta,
                            "indicator_count_delta": result.complexity_report.indicator_count_delta,
                            "feature_count_delta": result.complexity_report.feature_count_delta,
                            "cyclomatic_approx": result.complexity_report.cyclomatic_approx,
                            "score": result.complexity_report.score,
                        }
                        if result.complexity_report
                        else {}
                    ),
                    json.dumps(
                        {k: str(v) for k, v in result.artifacts.items()}
                    ),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            # Append to audit log
            self._log_transition(
                conn,
                result.run_id,
                "PENDING",
                result.status.value,
                result.rejection_reason or result.promoted_to or "",
            )

    def get(self, run_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM candidates WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_status(
        self, run_id: str, new_status: CandidateStatus, reason: str = ""
    ) -> None:
        with self._conn() as conn:
            old = conn.execute(
                "SELECT status FROM candidates WHERE run_id = ?", (run_id,)
            ).fetchone()
            old_status = old["status"] if old else "UNKNOWN"
            conn.execute(
                "UPDATE candidates SET status = ?, updated_at = ? WHERE run_id = ?",
                (
                    new_status.value,
                    datetime.now(timezone.utc).isoformat(),
                    run_id,
                ),
            )
            self._log_transition(conn, run_id, old_status, new_status.value, reason)

    def attach_probation_config(self, run_id: str, config: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE candidates SET probation_config_json = ? WHERE run_id = ?",
                (json.dumps(config), run_id),
            )

    def attach_note(self, run_id: str, note: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE candidates SET notes = ? WHERE run_id = ?",
                (note, run_id),
            )

    def list_by_status(self, status: CandidateStatus) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE status = ? ORDER BY created_at DESC",
                (status.value,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_approved_baseline(self) -> Optional[dict]:
        """Return the most recently approved candidate (the current baseline)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM candidates WHERE status = ? ORDER BY updated_at DESC LIMIT 1",
                (CandidateStatus.APPROVED.value,),
            ).fetchone()
        return dict(row) if row else None

    def get_audit_log(self, run_id: str) -> list[dict]:
        """Return all status transitions for a given run_id."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE run_id = ? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _log_transition(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        old_status: str,
        new_status: str,
        reason: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_log (run_id, old_status, new_status, reason, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                old_status,
                new_status,
                reason,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    run_id TEXT PRIMARY KEY,
                    hypothesis TEXT,
                    status TEXT NOT NULL,
                    rejection_reason TEXT,
                    promoted_to TEXT,

                    -- Lineage (new in v2)
                    baseline_run_id TEXT,
                    parent_commit TEXT,
                    candidate_commit TEXT,
                    strategy_fingerprint TEXT,
                    search_space_version TEXT,
                    scorecard_version TEXT,

                    -- Metrics
                    metric_deltas_json TEXT,
                    complexity_json TEXT,
                    artifacts_json TEXT,

                    -- Probation
                    probation_config_json TEXT,
                    notes TEXT,

                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    old_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_run_id ON audit_log(run_id)"
            )
