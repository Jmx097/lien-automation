"""
Queue API

Public functions for enqueuing scraping jobs.  Import these in
``main.py`` or any other entry-point.

Example::

    from src.queue.api import enqueue_window

    task_id = enqueue_window("20", "01/01/2026", "01/31/2026")
"""

import logging
from typing import Optional

from .models import Task
from .store import TaskStore

logger = logging.getLogger(__name__)


def enqueue_window(
    site_id: str,
    date_start: str,
    date_end: str,
    max_records: int = 50,
    db_path: Optional[str] = None,
) -> str:
    """Create a new pending task for the given site and date window.

    Args:
        site_id:     Site code (e.g. ``"12"``, ``"20"``).
        date_start:  Start of scrape window (``MM/DD/YYYY``).
        date_end:    End of scrape window (``MM/DD/YYYY``).
        max_records: Maximum records to fetch in one run.
        db_path:     Override the default SQLite path if needed.

    Returns:
        The hex task ID that was enqueued.
    """
    kwargs = {} if db_path is None else {"db_path": db_path}
    store = TaskStore(**kwargs)

    task = Task(
        site_id=site_id,
        date_start=date_start,
        date_end=date_end,
        max_records=max_records,
    )
    store.add_task(task)
    logger.info(
        "Enqueued task %s  site=%s  window=%s → %s  max=%d",
        task.id[:8],
        site_id,
        date_start,
        date_end,
        max_records,
    )
    return task.id
