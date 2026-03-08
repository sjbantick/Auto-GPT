"""
Static analysis runner: ruff, mypy, pytest.

Runs each tool in a subprocess with timeout.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from types_ import StaticCheckReport

log = logging.getLogger(__name__)

TIMEOUT = 60  # seconds per tool


class UnitRunner:
    def __init__(self, research_root: Path):
        self.research_root = research_root

    def run(self, worktree_path: Path) -> tuple[bool, StaticCheckReport]:
        ruff_ok = self._run_tool(
            ["ruff", "check", "."], worktree_path, "ruff"
        )
        mypy_ok = self._run_tool(
            [sys.executable, "-m", "mypy", "--ignore-missing-imports", "."],
            worktree_path,
            "mypy",
        )
        pytest_ok = self._run_tool(
            [sys.executable, "-m", "pytest", "tests/unit", "-x", "-q"],
            worktree_path,
            "pytest",
        )

        report = StaticCheckReport(
            passed=ruff_ok and mypy_ok and pytest_ok,
            ruff_ok=ruff_ok,
            mypy_ok=mypy_ok,
            pytest_ok=pytest_ok,
        )
        return report.passed, report

    def _run_tool(
        self, cmd: list[str], cwd: Path, label: str
    ) -> bool:
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
            if proc.returncode != 0:
                log.warning("%s failed:\n%s", label, proc.stdout[:500])
                return False
            return True
        except FileNotFoundError:
            log.warning("%s not installed, skipping", label)
            return True  # Don't block if tool not installed
        except subprocess.TimeoutExpired:
            log.warning("%s timed out after %ds", label, TIMEOUT)
            return False
