"""
Patch generation and application.

Extracts a unified diff from agent output and applies it
to the sandbox worktree via `git apply`.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)


class PatchManager:
    def __init__(self, baseline_strategy_path: Path):
        self.baseline_path = baseline_strategy_path

    def apply_hypothesis(
        self,
        hypothesis: str,
        worktree_path: Path,
        agent: Optional[Callable] = None,
    ) -> Optional[Path]:
        """
        Given a hypothesis (and optionally an agent callable to produce the patch),
        extract the unified diff and apply it to the worktree.

        Returns path to the saved .patch file, or None on failure.
        """
        if agent is not None:
            # Agent returns a response containing a diff block
            response = agent(hypothesis)
            patch_text = self._extract_diff(response)
        else:
            patch_text = self._extract_diff(hypothesis)

        if not patch_text:
            log.error("No valid diff found in agent response")
            return None

        # Save patch to file
        patch_file = worktree_path / ".candidate.patch"
        patch_file.write_text(patch_text)

        # Apply patch
        try:
            subprocess.run(
                ["git", "apply", "--check", str(patch_file)],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "apply", str(patch_file)],
                cwd=worktree_path,
                check=True,
                capture_output=True,
                text=True,
            )
            log.info("Patch applied successfully")
            return patch_file
        except subprocess.CalledProcessError as e:
            log.error("Patch apply failed: %s", e.stderr[:500] if e.stderr else str(e))
            return None

    @staticmethod
    def _extract_diff(text: str) -> Optional[str]:
        """Extract unified diff block from agent response text."""
        # Try fenced code block first
        match = re.search(
            r"```(?:diff)?\s*\n(---.*?)```",
            text,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # Try raw diff (starts with --- a/)
        match = re.search(
            r"(---\s+a/.*?(?=\n(?:---\s+a/|\Z)))",
            text,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        return None
