"""
Git worktree-based isolation for candidate evaluation.

Each experiment gets its own worktree so the orchestrator's
working tree is never polluted by candidate code.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class GitSandbox:
    """
    Context manager that creates an isolated git worktree for one experiment.

    Usage:
        with GitSandbox(research_root, run_id) as sandbox:
            sandbox.worktree_path  # Path to isolated copy
            # ... run evaluation ...
        # worktree is cleaned up unless preserve() was called
    """

    def __init__(self, research_root: Path, run_id: str):
        self.research_root = research_root.resolve()
        self.run_id = run_id
        self._worktree_dir = self.research_root / ".sandboxes" / run_id
        self._branch_name = f"autoresearch/{run_id}"
        self._preserved = False

    @property
    def worktree_path(self) -> Path:
        return self._worktree_dir

    def __enter__(self) -> GitSandbox:
        self._worktree_dir.parent.mkdir(parents=True, exist_ok=True)

        # Create a detached worktree from HEAD
        subprocess.run(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(self._worktree_dir),
                "HEAD",
            ],
            cwd=self.research_root,
            check=True,
            capture_output=True,
        )
        log.info("Created sandbox worktree at %s", self._worktree_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._preserved:
            self._cleanup()

    def preserve(self) -> None:
        """Keep the worktree after exit (for paper-stage promotion)."""
        self._preserved = True
        log.info("Sandbox %s marked for preservation", self.run_id)

    def get_commit_sha(self) -> Optional[str]:
        """Return the HEAD commit SHA of the worktree."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self._worktree_dir,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def commit_candidate(self, message: str) -> Optional[str]:
        """Stage and commit all changes in the worktree. Returns SHA."""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=self._worktree_dir,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message, "--allow-empty"],
                cwd=self._worktree_dir,
                check=True,
                capture_output=True,
            )
            return self.get_commit_sha()
        except subprocess.CalledProcessError as e:
            log.warning("Commit failed in sandbox: %s", e)
            return None

    def _cleanup(self) -> None:
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(self._worktree_dir)],
                cwd=self.research_root,
                capture_output=True,
            )
        except Exception:
            pass
        if self._worktree_dir.exists():
            shutil.rmtree(self._worktree_dir, ignore_errors=True)
        log.info("Cleaned up sandbox %s", self.run_id)
