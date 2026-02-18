"""
Queue Task Model

Defines the Task dataclass used throughout the queue system
to represent a single scraping job.
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Task:
    """A single lien-scraping job targeting one site over a date window.

    Attributes:
        id:          Unique task identifier (UUID4 hex string).
        site_id:     Site code matching config/sites.json (e.g. "12", "20").
        date_start:  Inclusive start of the scrape window (MM/DD/YYYY).
        date_end:    Inclusive end of the scrape window (MM/DD/YYYY).
        max_records: Cap on records to retrieve in one run.
        cursor:      Opaque resume token (page number, offset, etc.).
        status:      One of: pending, running, completed, failed.
        attempts:    Number of times this task has been attempted.
        last_error:  Error message from the most recent failure.
        created_at:  ISO-8601 timestamp of task creation.
        updated_at:  ISO-8601 timestamp of last status change.
    """

    site_id: str
    date_start: str
    date_end: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    max_records: int = 50
    cursor: str = ""
    status: str = "pending"
    attempts: int = 0
    last_error: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain dict representation of the task."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Construct a Task from a dict (e.g. from JSON or a DB row)."""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp to *now*."""
        self.updated_at = datetime.now(timezone.utc).isoformat()
