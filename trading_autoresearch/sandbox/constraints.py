"""
Path-level scope enforcement with hardened diff parsing and precise AST checks.

Fixes vs v1:
  - Proper unified-diff parsing: handles a/b/ prefixes, /dev/null, renames
  - Tracks unique changed files, not raw diff header lines
  - AST checks are precise: only flags subprocess.run/Popen/call, os.system,
    builtins eval/exec — does NOT flag arbitrary .run() or .call() methods
  - Inspects only MODIFIED editable files, not the entire editable tree
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path
from typing import Optional

from sandbox.forbidden_paths import (
    EDITABLE_ROOTS,
    FORBIDDEN_IMPORT_PATTERNS,
    FORBIDDEN_ROOTS,
    MAX_NEW_FILES,
    MAX_PATCH_LINES,
)
from types_ import ComplexityReport, ScopeReport, ScopeViolation

log = logging.getLogger(__name__)


class ScopeValidator:
    def __init__(self, research_root: Path):
        self.research_root = research_root.resolve()
        self._forbidden_import_re = [
            re.compile(p, re.MULTILINE) for p in FORBIDDEN_IMPORT_PATTERNS
        ]

    def validate(
        self,
        worktree_path: Path,
        patch_path: Optional[Path],
    ) -> tuple[bool, ScopeReport]:
        report = ScopeReport(valid=True)

        if patch_path is None or not patch_path.exists():
            report.valid = False
            report.violations.append(ScopeViolation("patch", "No patch file found"))
            return False, report

        patch_text = patch_path.read_text()
        report.patch_line_count = patch_text.count("\n")

        # ── Patch size ────────────────────────────────────────────────────
        if report.patch_line_count > MAX_PATCH_LINES:
            report.valid = False
            report.violations.append(
                ScopeViolation(
                    "patch",
                    f"Patch too large: {report.patch_line_count} lines "
                    f"(max {MAX_PATCH_LINES})",
                )
            )

        # ── Parse changed files from unified diff ─────────────────────────
        changed_files, new_files, deleted_files = self._parse_unified_diff(patch_text)
        report.changed_files = list(changed_files)
        report.new_files_added = len(new_files)

        if report.new_files_added > MAX_NEW_FILES:
            report.valid = False
            report.violations.append(
                ScopeViolation(
                    "patch",
                    f"Too many new files: {report.new_files_added} "
                    f"(max {MAX_NEW_FILES})",
                )
            )

        # ── Check each changed file against path policy ───────────────────
        for file_path in changed_files:
            if self._is_forbidden(file_path):
                report.valid = False
                report.violations.append(
                    ScopeViolation(file_path, "Touches forbidden path")
                )
            elif not self._is_editable(file_path):
                report.valid = False
                report.violations.append(
                    ScopeViolation(file_path, "Outside editable scope")
                )

        # ── Check forbidden imports only in MODIFIED editable Python files ─
        modified_py = [
            f for f in changed_files
            if f.endswith(".py") and self._is_editable(f)
        ]
        for rel_path in modified_py:
            full_path = worktree_path / rel_path
            if not full_path.exists():
                continue
            source = full_path.read_text(errors="replace")
            for pattern in self._forbidden_import_re:
                if pattern.search(source):
                    report.valid = False
                    report.violations.append(
                        ScopeViolation(
                            rel_path,
                            f"Forbidden import pattern: {pattern.pattern}",
                        )
                    )

        # ── AST safety check only on MODIFIED editable Python files ───────
        for rel_path in modified_py:
            full_path = worktree_path / rel_path
            if not full_path.exists():
                continue
            violation = self._ast_safety_check(full_path)
            if violation:
                report.valid = False
                report.violations.append(ScopeViolation(rel_path, violation))

        return report.valid, report

    def compute_complexity(
        self,
        worktree_path: Path,
        baseline_path: Path,
        changed_files: list[str],
        patch_text: str,
    ) -> ComplexityReport:
        """
        Compute a richer complexity measure than raw LOC.

        Compares candidate vs baseline on:
        - lines changed (from patch)
        - new parameters (function default args)
        - branch count delta (if/for/while/except/and/or)
        - indicator count delta (heuristic: calls to ta.* or TA-Lib-like)
        - feature count delta (functions named *feature* / *feat*)
        - approximate cyclomatic complexity
        """
        lines_changed = sum(
            1
            for line in patch_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

        candidate_stats = self._ast_stats(worktree_path, changed_files)
        baseline_stats = self._ast_stats(baseline_path, changed_files)

        return ComplexityReport(
            lines_changed=lines_changed,
            new_parameters=candidate_stats["params"] - baseline_stats["params"],
            branch_count_delta=candidate_stats["branches"] - baseline_stats["branches"],
            indicator_count_delta=candidate_stats["indicators"] - baseline_stats["indicators"],
            feature_count_delta=candidate_stats["features"] - baseline_stats["features"],
            cyclomatic_approx=candidate_stats["branches"],
        )

    # ── Diff parsing ──────────────────────────────────────────────────────────

    def _parse_unified_diff(
        self, patch_text: str
    ) -> tuple[set[str], set[str], set[str]]:
        """
        Parse unified diff to extract changed, new, and deleted files.
        Handles:
          - a/ b/ prefixes (git diff format)
          - /dev/null for new or deleted files
          - Renames
        Returns (all_changed, new_files, deleted_files) with normalized paths.
        """
        changed: set[str] = set()
        new_files: set[str] = set()
        deleted_files: set[str] = set()

        lines = patch_text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("--- "):
                old_path = self._normalize_diff_path(line[4:].strip())
                new_path = None
                if i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
                    new_path = self._normalize_diff_path(lines[i + 1][4:].strip())
                    i += 1

                if old_path == "/dev/null" and new_path and new_path != "/dev/null":
                    new_files.add(new_path)
                    changed.add(new_path)
                elif new_path == "/dev/null" and old_path and old_path != "/dev/null":
                    deleted_files.add(old_path)
                    changed.add(old_path)
                else:
                    if old_path and old_path != "/dev/null":
                        changed.add(old_path)
                    if new_path and new_path != "/dev/null":
                        changed.add(new_path)
            i += 1

        return changed, new_files, deleted_files

    @staticmethod
    def _normalize_diff_path(raw: str) -> str:
        """Strip a/ or b/ prefix from git diff paths."""
        # Handle quoted paths
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        # Strip a/ or b/ prefix
        if raw.startswith("a/") or raw.startswith("b/"):
            return raw[2:]
        return raw

    # ── Path policy checks ────────────────────────────────────────────────────

    @staticmethod
    def _is_forbidden(path: str) -> bool:
        return any(path.startswith(root) for root in FORBIDDEN_ROOTS)

    @staticmethod
    def _is_editable(path: str) -> bool:
        return any(path.startswith(root) for root in EDITABLE_ROOTS)

    # ── AST safety (precise, no false positives) ──────────────────────────────

    @staticmethod
    def _ast_safety_check(py_file: Path) -> Optional[str]:
        """
        Detect genuinely dangerous AST patterns.

        ONLY flags:
          - subprocess.run / subprocess.Popen / subprocess.call
          - os.system / os.popen
          - builtins eval() / exec()
          - __import__

        Does NOT flag arbitrary .run() or .call() method calls on
        user-defined objects — that would cause false positives.
        """
        try:
            source = py_file.read_text()
            tree = ast.parse(source)
        except SyntaxError as e:
            return f"Syntax error: {e}"

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func

            # eval(...) / exec(...) as bare name calls
            if isinstance(func, ast.Name) and func.id in ("eval", "exec"):
                return f"Forbidden builtin call: {func.id}()"

            # __import__(...)
            if isinstance(func, ast.Name) and func.id == "__import__":
                return "Forbidden: __import__()"

            # subprocess.run / subprocess.Popen / subprocess.call
            # os.system / os.popen
            if isinstance(func, ast.Attribute):
                # Check the object the method is called on
                if isinstance(func.value, ast.Name):
                    obj_name = func.value.id
                    method_name = func.attr
                    if obj_name == "subprocess" and method_name in (
                        "run",
                        "Popen",
                        "call",
                        "check_call",
                        "check_output",
                    ):
                        return f"Forbidden: subprocess.{method_name}()"
                    if obj_name == "os" and method_name in ("system", "popen"):
                        return f"Forbidden: os.{method_name}()"

        return None

    # ── AST stats for complexity measure ──────────────────────────────────────

    @staticmethod
    def _ast_stats(root: Path, rel_files: list[str]) -> dict[str, int]:
        stats = {"params": 0, "branches": 0, "indicators": 0, "features": 0}
        for rel in rel_files:
            if not rel.endswith(".py"):
                continue
            full = root / rel
            if not full.exists():
                continue
            try:
                tree = ast.parse(full.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    stats["params"] += len(node.args.defaults) + len(
                        node.args.kw_defaults
                    )
                    name = node.name.lower()
                    if "feature" in name or "feat" in name:
                        stats["features"] += 1
                if isinstance(
                    node,
                    (
                        ast.If,
                        ast.For,
                        ast.While,
                        ast.ExceptHandler,
                        ast.BoolOp,
                    ),
                ):
                    stats["branches"] += 1
                # Heuristic: calls to ta.something / talib.something
                if isinstance(node, ast.Call) and isinstance(
                    node.func, ast.Attribute
                ):
                    if isinstance(node.func.value, ast.Name):
                        if node.func.value.id.lower() in ("ta", "talib"):
                            stats["indicators"] += 1
        return stats
