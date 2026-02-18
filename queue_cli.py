#!/usr/bin/env python3
"""
Queue CLI — manage the lien-scraping task queue from the terminal.

Commands:
    enqueue   Add a new scraping job for a site + date window.
    run-once  Pick the next pending task and execute it.
    list      Show tasks in the queue (optionally filtered by status).

Usage examples::

    python queue_cli.py enqueue --site 20 --start "01/01/2026" --end "01/31/2026"
    python queue_cli.py run-once
    python queue_cli.py list --status pending
"""

import argparse
import sys
import os

# Ensure repo root is on sys.path so `src.*` imports work.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.queue.api import enqueue_window          # noqa: E402
from src.queue.store import TaskStore              # noqa: E402
from src.queue.worker import run_task              # noqa: E402


# ------------------------------------------------------------------
# Subcommand handlers
# ------------------------------------------------------------------

def _handle_enqueue(args: argparse.Namespace) -> None:
    """Handler for the ``enqueue`` subcommand."""
    task_id = enqueue_window(
        site_id=args.site,
        date_start=args.start,
        date_end=args.end,
        max_records=args.max_records,
    )
    print(f"✓ Enqueued task {task_id[:8]}…  (site={args.site})")


def _handle_run_once(args: argparse.Namespace) -> None:
    """Handler for the ``run-once`` subcommand."""
    store = TaskStore()
    task = store.get_next_pending()
    if task is None:
        print("No pending tasks in the queue.")
        return
    print(
        f"Running task {task.id[:8]}…  "
        f"(site={task.site_id}, attempt {task.attempts + 1})"
    )
    run_task(task, store)
    # Re-fetch to show final status
    updated = [t for t in store.list_tasks() if t.id == task.id]
    if updated:
        print(f"→ Final status: {updated[0].status}")


def _handle_list(args: argparse.Namespace) -> None:
    """Handler for the ``list`` subcommand."""
    store = TaskStore()
    tasks = store.list_tasks(status=args.status)
    if not tasks:
        label = f" with status='{args.status}'" if args.status else ""
        print(f"No tasks found{label}.")
        return

    # Header
    fmt = "{:<10} {:<8} {:<12} {:<12} {:<11} {:<4} {}"
    print(fmt.format("ID", "SITE", "START", "END", "STATUS", "ATT", "LAST ERROR"))
    print("-" * 80)
    for t in tasks:
        error_preview = (t.last_error[:30] + "…") if len(t.last_error) > 30 else t.last_error
        print(
            fmt.format(
                t.id[:10],
                t.site_id,
                t.date_start,
                t.date_end,
                t.status,
                t.attempts,
                error_preview,
            )
        )


# ------------------------------------------------------------------
# Argument parser
# ------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="queue_cli",
        description="Manage the lien-scraping task queue.",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # -- enqueue --
    enq = subs.add_parser("enqueue", help="Add a scraping job to the queue.")
    enq.add_argument("--site", required=True, help="Site ID (e.g. 12, 20)")
    enq.add_argument("--start", required=True, help="Start date (MM/DD/YYYY)")
    enq.add_argument("--end", required=True, help="End date (MM/DD/YYYY)")
    enq.add_argument(
        "--max-records", type=int, default=50, help="Max records (default 50)"
    )

    # -- run-once --
    subs.add_parser("run-once", help="Execute the next pending task.")

    # -- list --
    lst = subs.add_parser("list", help="List tasks in the queue.")
    lst.add_argument(
        "--status",
        choices=["pending", "running", "completed", "failed"],
        default=None,
        help="Filter by status",
    )

    return parser


def main() -> None:
    """CLI entry-point."""
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "enqueue": _handle_enqueue,
        "run-once": _handle_run_once,
        "list": _handle_list,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
