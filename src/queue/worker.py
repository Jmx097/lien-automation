"""
Queue Worker

Executes a single Task by calling the appropriate scraper, writing
results to Google Sheets, and updating the task status with retry logic.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List

from .models import Task
from .store import TaskStore

logger = logging.getLogger(__name__)

# Maximum number of attempts before marking a task as failed.
MAX_ATTEMPTS = 3

# Google Sheet ID (same default used in main.py)
SHEET_ID = os.getenv("SHEETS_ID", "18C3Qrk3rEXZ9oNocIEUugFLh6q38DRw9JVwznTHoRN0")


# ------------------------------------------------------------------
# Scraper dispatch
# ------------------------------------------------------------------

async def _scrape_nyc_acris(task: Task) -> List[Any]:
    """Run the NYC ACRIS scraper and return raw record objects."""
    from src.browser_automation import scrape_nyc_acris  # lazy import

    records = await scrape_nyc_acris()
    return records


async def _scrape_ca_ucc(task: Task) -> List[Dict[str, Any]]:
    """Run the CA UCC Playwright scraper for the task's date window."""
    from src.scrapers.ca_ucc_scraper_playwright import CAUCCScraper  # lazy

    scrapingbee_key = os.getenv("SCRAPINGBEE_API_KEY", "")
    if not scrapingbee_key:
        raise RuntimeError("SCRAPINGBEE_API_KEY environment variable is not set")

    async with CAUCCScraper(api_key=scrapingbee_key) as scraper:
        lien_records, _debug = await scraper.scrape_debug(
            from_date=task.date_start,
            to_date=task.date_end,
            max_results=task.max_records,
        )

    # Return list of dicts for downstream processing
    return [r.to_dict() for r in lien_records]


_SCRAPER_DISPATCH = {
    "12": _scrape_nyc_acris,
    "20": _scrape_ca_ucc,
}


# ------------------------------------------------------------------
# Sheets integration
# ------------------------------------------------------------------

def _write_to_sheets(records: List[Any], site_id: str) -> int:
    """Append records to Google Sheets.  Returns count written."""
    if not records:
        return 0

    from src.sheets_integration import GoogleSheetsIntegration
    from src.field_mapper import FieldMapper

    site_key = {"12": "nyc_acris", "10": "cook_county", "20": "ca_sos"}.get(
        site_id, "unknown"
    )

    mapper = FieldMapper(site_key)
    rows: List[list] = []
    mapper = FieldMapper(site_key)
    rows: List[list] = []
    for rec in records:
        # Convert dictionary or object to dict
        rec_dict = rec if isinstance(rec, dict) else (rec.to_dict() if hasattr(rec, 'to_dict') else rec.__dict__)

        # Map CA UCC fields to mapper expected keys
        extracted_fields = {}
        if site_id == "20":
            extracted_fields = {
                "taxpayer_name": rec_dict.get("debtor_name", ""),
                "address": rec_dict.get("debtor_address", ""),
                "city_state_zip": rec_dict.get("debtor_address", ""),  # Use full address for parsing
                "lien_date": rec_dict.get("filing_date", ""),
                "amount": "",  # CA UCC scraper currently doesn't provide amount
            }

        raw_text = json.dumps(rec_dict)
        mapped = mapper.map_record(extracted_fields, raw_text)
        rows.append(mapped.to_row())

    sheets = GoogleSheetsIntegration(SHEET_ID)
    result = sheets.write_liens(rows)
    logger.info(
        "Sheets write: %d written, %d duplicates skipped",
        result.rows_written,
        result.duplicates_skipped,
    )
    return result.rows_written


# ------------------------------------------------------------------
# Core entry-point
# ------------------------------------------------------------------

def run_task(task: Task, store: TaskStore) -> None:
    """Execute a single queued task with retry + exponential backoff.

    Workflow:
        1. Mark task as ``running`` and increment ``attempts``.
        2. Dispatch to the appropriate scraper.
        3. Write results to Google Sheets.
        4. On success → ``completed``; on failure → re-queue as
           ``pending`` (up to ``MAX_ATTEMPTS``), then ``failed``.

    Args:
        task:  The :class:`Task` to execute.
        store: A :class:`TaskStore` used to persist status changes.
    """
    scraper_fn = _SCRAPER_DISPATCH.get(task.site_id)
    if scraper_fn is None:
        logger.error("No scraper registered for site_id=%s", task.site_id)
        task.status = "failed"
        task.last_error = f"Unsupported site_id: {task.site_id}"
        store.update_task(task)
        return

    task.status = "running"
    task.attempts += 1
    store.update_task(task)
    logger.info(
        "Running task %s (site=%s, attempt %d/%d)",
        task.id[:8],
        task.site_id,
        task.attempts,
        MAX_ATTEMPTS,
    )

    try:
        records = asyncio.run(scraper_fn(task))
        written = _write_to_sheets(records, task.site_id)

        task.status = "completed"
        task.cursor = f"records_written={written}"
        task.last_error = ""
        store.update_task(task)
        logger.info("Task %s completed (%d records written)", task.id[:8], written)

    except Exception as exc:
        import traceback
        logger.error(
            "Task %s failed: %s\n%s", task.id[:8], exc, traceback.format_exc()
        )
        task.last_error = f"{str(exc)}\n{traceback.format_exc()}"
        
        if task.attempts >= MAX_ATTEMPTS:
            task.status = "failed"
            store.update_task(task)
            logger.warning(
                "Task %s permanently failed after %d attempts",
                task.id[:8],
                task.attempts,
            )
        else:
            task.status = "pending"
            store.update_task(task)
            backoff = 2 ** task.attempts
            logger.info(
                "Task %s will retry (backoff %ds)", task.id[:8], backoff
            )
            time.sleep(backoff)
