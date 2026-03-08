#!/usr/bin/env python3
"""
CLI entry point for the trading autoresearch framework.

Usage:
    # Run one research iteration with a manual hypothesis
    python run_loop.py run --hypothesis "Add volume filter to RSI signals"

    # Run N autonomous iterations (requires agent callable)
    python run_loop.py run --iterations 5

    # Dry run (skip actual backtests)
    python run_loop.py run --hypothesis "test" --dry-run

    # Check candidate status
    python run_loop.py status --run-id <run_id>

    # Promote a candidate (requires --approve for human gates)
    python run_loop.py promote --run-id <run_id> --approve

    # Show leaderboard
    python run_loop.py leaderboard

    # Show audit log for a run
    python run_loop.py audit --run-id <run_id>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure the package root is on sys.path
sys.path.insert(0, str(Path(__file__).parent))

from orchestrator.loop import LoopConfig, ResearchLoop
from orchestrator.candidate_registry import CandidateRegistry
from orchestrator.promotion_manager import PromotionManager
from reports.leaderboard import Leaderboard
from types_ import CandidateStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("autoresearch")


def cmd_run(args: argparse.Namespace) -> None:
    research_root = Path(args.root).resolve()
    config = LoopConfig(
        baseline_strategy_path=research_root / "strategies" / "baseline",
        research_root=research_root,
        max_iterations=args.iterations,
        dry_run=args.dry_run,
    )
    loop = ResearchLoop(config)

    if args.hypothesis:
        result = loop.run_iteration(hypothesis=args.hypothesis)
        print(f"\nResult: {result.status.value}")
        if result.rejection_reason:
            print(f"Reason: {result.rejection_reason}")
        if result.promoted_to:
            print(f"Promoted to: {result.promoted_to}")
        print(f"Run ID: {result.run_id}")
    else:
        results = loop.run_n_iterations(args.iterations)
        print(f"\nCompleted {len(results)} iterations.")
        for r in results:
            print(f"  {r.run_id}: {r.status.value}")


def cmd_status(args: argparse.Namespace) -> None:
    research_root = Path(args.root).resolve()
    registry = CandidateRegistry(research_root / ".candidates.db")
    candidate = registry.get(args.run_id)
    if candidate is None:
        print(f"No candidate found with run_id: {args.run_id}")
        sys.exit(1)
    print(json.dumps(dict(candidate), indent=2, default=str))


def cmd_promote(args: argparse.Namespace) -> None:
    research_root = Path(args.root).resolve()
    registry = CandidateRegistry(research_root / ".candidates.db")
    manager = PromotionManager(registry)

    try:
        new_status, message = manager.promote(
            run_id=args.run_id,
            human_approved=args.approve,
        )
        print(message)
    except PermissionError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def cmd_leaderboard(args: argparse.Namespace) -> None:
    research_root = Path(args.root).resolve()
    registry = CandidateRegistry(research_root / ".candidates.db")
    lb = Leaderboard(registry)
    print(lb.print_top(args.top))


def cmd_audit(args: argparse.Namespace) -> None:
    research_root = Path(args.root).resolve()
    registry = CandidateRegistry(research_root / ".candidates.db")
    log_entries = registry.get_audit_log(args.run_id)
    if not log_entries:
        print(f"No audit log for run_id: {args.run_id}")
        return
    for entry in log_entries:
        print(
            f"  {entry['timestamp']} | "
            f"{entry['old_status']} -> {entry['new_status']} | "
            f"{entry['reason']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trading Autoresearch Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Research root directory (default: current directory)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # run
    run_p = sub.add_parser("run", help="Run research iterations")
    run_p.add_argument("--hypothesis", type=str, help="Manual hypothesis")
    run_p.add_argument(
        "--iterations", type=int, default=1, help="Number of iterations"
    )
    run_p.add_argument(
        "--dry-run", action="store_true", help="Skip actual backtests"
    )

    # status
    status_p = sub.add_parser("status", help="Check candidate status")
    status_p.add_argument("--run-id", required=True, help="Run ID to check")

    # promote
    promote_p = sub.add_parser("promote", help="Promote a candidate")
    promote_p.add_argument("--run-id", required=True, help="Run ID to promote")
    promote_p.add_argument(
        "--approve",
        action="store_true",
        help="Explicit human approval (required for paper_approved+)",
    )

    # leaderboard
    lb_p = sub.add_parser("leaderboard", help="Show candidate leaderboard")
    lb_p.add_argument("--top", type=int, default=10, help="Number of entries")

    # audit
    audit_p = sub.add_parser("audit", help="Show audit log for a run")
    audit_p.add_argument("--run-id", required=True, help="Run ID to audit")

    args = parser.parse_args()

    commands = {
        "run": cmd_run,
        "status": cmd_status,
        "promote": cmd_promote,
        "leaderboard": cmd_leaderboard,
        "audit": cmd_audit,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
