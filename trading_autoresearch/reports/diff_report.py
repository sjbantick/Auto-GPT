"""Human-readable diff report for candidate patches."""

from __future__ import annotations

from pathlib import Path


def generate_diff_report(patch_path: Path) -> str:
    """Read a patch file and format it for human review."""
    if not patch_path.exists():
        return "No patch file found."
    patch_text = patch_path.read_text()
    return f"## Candidate Patch\n\n```diff\n{patch_text}\n```"
