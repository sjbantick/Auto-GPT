"""
Anti-lookahead and anti-leakage validation.

Checks candidate strategy code for common data leakage patterns:
  - Future bar access (df.iloc[i+N] in signal logic)
  - Accidental lookahead via improper shift() usage
  - Feature leakage (using target/label columns in features)
  - Future-indexed value access
  - Improper label alignment

This is a best-effort static analysis. It catches common mistakes
but cannot guarantee absence of all leakage. Critical strategies
should also be manually reviewed.
"""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

from types_ import LeakageReport, LeakageWarning

log = logging.getLogger(__name__)

# ── Pattern-based checks (regex on source) ────────────────────────────────────

# These patterns indicate common lookahead / leakage mistakes
_SOURCE_PATTERNS: list[tuple[str, str, str]] = [
    # (regex, description, severity)
    (
        r"\.shift\(\s*-\d+",
        "Negative shift may indicate future data access",
        "error",
    ),
    (
        r"\.iloc\[\s*[a-zA-Z_]+\s*\+\s*\d+",
        "Forward iloc indexing (i+N) may access future bars",
        "error",
    ),
    (
        r"\.loc\[.*\+.*timedelta",
        "Forward timedelta in .loc may access future data",
        "warning",
    ),
    (
        r"df\[.*(target|label|y_true|future|forward).*\]",
        "Possible use of target/label column in feature computation",
        "error",
    ),
    (
        r"\.(pct_change|diff|rolling|ewm)\(.*\)\.shift\(\s*-",
        "Negative shift after transform may leak future values",
        "error",
    ),
    (
        r"\.resample\(.*\)\.(mean|sum|std|var)\(\)(?!.*\.shift\()",
        "Resample aggregate without shift — check for lookahead",
        "warning",
    ),
    (
        r"train.*test.*split.*shuffle\s*=\s*True",
        "Shuffled train/test split on time series causes leakage",
        "error",
    ),
    (
        r"StandardScaler|MinMaxScaler|RobustScaler",
        "Scaler should be fit on train only, not full dataset",
        "warning",
    ),
    (
        r"\.fit_transform\(",
        "fit_transform on full dataset may cause train/test leakage",
        "warning",
    ),
]


# ── AST-based checks ─────────────────────────────────────────────────────────

class _LeakageVisitor(ast.NodeVisitor):
    """AST visitor that flags suspicious lookahead patterns."""

    def __init__(self, filename: str):
        self.filename = filename
        self.warnings: list[LeakageWarning] = []

    def visit_Subscript(self, node: ast.Subscript) -> None:
        """Check for forward indexing patterns like data[i+1]."""
        if isinstance(node.slice, ast.BinOp):
            if isinstance(node.slice.op, ast.Add):
                # Check if right side is a positive constant
                if isinstance(node.slice.right, ast.Constant):
                    if isinstance(node.slice.right.value, (int, float)):
                        if node.slice.right.value > 0:
                            self.warnings.append(
                                LeakageWarning(
                                    file=self.filename,
                                    line=node.lineno,
                                    pattern="forward_index",
                                    description=(
                                        f"Forward indexing detected (+ {node.slice.right.value}). "
                                        "Verify this does not access future data."
                                    ),
                                )
                            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check for shift(-N) calls."""
        if isinstance(node.func, ast.Attribute) and node.func.attr == "shift":
            if node.args:
                arg = node.args[0]
                # shift(-N) — negative shift means future access
                if isinstance(arg, ast.UnaryOp) and isinstance(
                    arg.op, ast.USub
                ):
                    if isinstance(arg.operand, ast.Constant):
                        self.warnings.append(
                            LeakageWarning(
                                file=self.filename,
                                line=node.lineno,
                                pattern="negative_shift",
                                description=(
                                    f"shift(-{arg.operand.value}) accesses future bars. "
                                    "Only use positive shift for lagging."
                                ),
                            )
                        )
                # shift(N) where N is negative constant
                if isinstance(arg, ast.Constant) and isinstance(
                    arg.value, (int, float)
                ):
                    if arg.value < 0:
                        self.warnings.append(
                            LeakageWarning(
                                file=self.filename,
                                line=node.lineno,
                                pattern="negative_shift",
                                description=(
                                    f"shift({arg.value}) accesses future bars. "
                                    "Only use positive shift for lagging."
                                ),
                            )
                        )
        self.generic_visit(node)


class LeakageChecker:
    """
    Runs static analysis on candidate strategy files to detect
    common lookahead bias and data leakage patterns.
    """

    def check(
        self,
        worktree_path: Path,
        changed_files: list[str],
    ) -> LeakageReport:
        """
        Check only the modified Python files for leakage patterns.

        Args:
            worktree_path: Root of the candidate worktree
            changed_files: Relative paths of files changed in the patch

        Returns:
            LeakageReport with pass/fail and detailed warnings
        """
        all_warnings: list[LeakageWarning] = []
        errors: list[LeakageWarning] = []

        py_files = [f for f in changed_files if f.endswith(".py")]

        for rel_path in py_files:
            full_path = worktree_path / rel_path
            if not full_path.exists():
                continue

            source = full_path.read_text(errors="replace")

            # Regex-based pattern checks
            for pattern, description, severity in _SOURCE_PATTERNS:
                for match in re.finditer(pattern, source, re.IGNORECASE):
                    line_no = source[:match.start()].count("\n") + 1
                    w = LeakageWarning(
                        file=rel_path,
                        line=line_no,
                        pattern=pattern[:40],
                        description=description,
                    )
                    all_warnings.append(w)
                    if severity == "error":
                        errors.append(w)

            # AST-based checks
            try:
                tree = ast.parse(source)
                visitor = _LeakageVisitor(rel_path)
                visitor.visit(tree)
                for w in visitor.warnings:
                    all_warnings.append(w)
                    errors.append(w)  # AST findings are always errors
            except SyntaxError:
                pass  # Syntax errors caught by unit_runner

        passed = len(errors) == 0

        if all_warnings:
            log.info("Leakage check found %d warnings:", len(all_warnings))
            for w in all_warnings:
                log.info("  %s:%d — %s", w.file, w.line, w.description)

        report = LeakageReport(passed=passed, warnings=all_warnings)
        return report
