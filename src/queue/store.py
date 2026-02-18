"""
SQLite-Backed Task Store

Provides durable persistence for queue Tasks using a local SQLite
database.  The database and table are created automatically on first use.
"""

import os
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional

from .models import Task

logger = logging.getLogger(__name__)

# Default database path (relative to repo root)
_DEFAULT_DB_PATH = os.path.join("data", "queue.db")


class TaskStore:
    """CRUD interface for queue :class:`Task` objects backed by SQLite.

    Args:
        db_path: Path to the SQLite database file.  Parent directories
                 are created automatically if they don't exist.
    """

    _CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS tasks (
        id          TEXT PRIMARY KEY,
        site_id     TEXT NOT NULL,
        date_start  TEXT NOT NULL,
        date_end    TEXT NOT NULL,
        max_records INTEGER NOT NULL DEFAULT 50,
        cursor      TEXT NOT NULL DEFAULT '',
        status      TEXT NOT NULL DEFAULT 'pending',
        attempts    INTEGER NOT NULL DEFAULT 0,
        last_error  TEXT NOT NULL DEFAULT '',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );
    """

    def __init__(self, db_path: str = _DEFAULT_DB_PATH) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(self._CREATE_TABLE)
        self._conn.commit()
        logger.info("TaskStore initialised (%s)", db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_task(self, task: Task) -> Task:
        """Insert a new task into the store.  Returns the same task."""
        self._conn.execute(
            """
            INSERT INTO tasks
                (id, site_id, date_start, date_end, max_records,
                 cursor, status, attempts, last_error,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.site_id,
                task.date_start,
                task.date_end,
                task.max_records,
                task.cursor,
                task.status,
                task.attempts,
                task.last_error,
                task.created_at,
                task.updated_at,
            ),
        )
        self._conn.commit()
        logger.info("Added task %s (site=%s)", task.id[:8], task.site_id)
        return task

    def get_next_pending(self) -> Optional[Task]:
        """Return the oldest task with ``status='pending'``, or *None*."""
        row = self._conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """,
        ).fetchone()
        if row is None:
            return None
        return Task.from_dict(dict(row))

    def update_task(self, task: Task) -> None:
        """Persist changes made to *task* (matched by ``id``)."""
        task.touch()
        self._conn.execute(
            """
            UPDATE tasks
            SET site_id     = ?,
                date_start  = ?,
                date_end    = ?,
                max_records = ?,
                cursor      = ?,
                status      = ?,
                attempts    = ?,
                last_error  = ?,
                updated_at  = ?
            WHERE id = ?
            """,
            (
                task.site_id,
                task.date_start,
                task.date_end,
                task.max_records,
                task.cursor,
                task.status,
                task.attempts,
                task.last_error,
                task.updated_at,
                task.id,
            ),
        )
        self._conn.commit()

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """Return tasks, optionally filtered by *status*."""
        if status:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC"
            ).fetchall()
        return [Task.from_dict(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()
