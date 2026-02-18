"""
California SOS UCC Lien Scraper — Playwright Version

Implements "Federal Tax Lien" search on bizfileonline.sos.ca.gov using
Playwright to handle the React SPA, finding records by date range,
extracting detail panel info, and downloading "View History" PDFs.

See spec for full details.
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

from playwright.async_api import (
    async_playwright,
    Page,
    BrowserContext,
    Browser,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Exceptions & Data Structures
# ------------------------------------------------------------------


class TooManyResultsError(Exception):
    """Raised when search returns > 1000 results."""


@dataclass
class LienRecord:
    """Represents a single scraped lien record."""

    state: str = "CA"
    ucc_type: str = ""
    debtor_name: str = ""
    debtor_address: str = ""
    file_number: str = ""
    secured_party_name: str = ""
    secured_party_address: str = ""
    status: str = ""
    filing_date: str = ""
    lapse_date: str = ""
    document_type: str = ""
    pdf_filename: str = ""
    processed: bool = False
    error: str = ""
    # Extra fields for debugging / context
    raw_debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ------------------------------------------------------------------
# Scraper Class
# ------------------------------------------------------------------


class CAUCCScraper:
    """Playwright-based scraper for CA SOS UCC Federal Tax Liens."""

    BASE_URL = "https://bizfileonline.sos.ca.gov/search/ucc"

    def __init__(self, api_key: Optional[str] = None):
        # api_key arg kept for signature compatibility, unused by direct Playwright
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def __aenter__(self):
        await self.init_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init_browser(self):
        """Launch browser and setup context with downloads."""
        if self.page:
            return

        self.playwright = await async_playwright().start()
        # Headless by default; set headless=False for local debugging
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context(accept_downloads=True)
        self.page = await self.context.new_page()

    async def close(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def scrape_debug(
        self,
        from_date: str,
        to_date: str,
        max_results: int = 50,
        page_number: int = 1,
    ) -> Tuple[List[LienRecord], Dict[str, Any]]:
        """
        Main entry point. Scrapes CA UCC liens for the given date range.

        Args:
            from_date: "MM/DD/YYYY"
            to_date:   "MM/DD/YYYY"
            max_results: Cap on collected records.
            page_number: 1-based start page (resume capability).

        Returns:
            (records, debug_info_dict)
        """
        if not self.page:
            await self.init_browser()

        records: List[LienRecord] = []
        debug_info = {"pages_visited": 0, "errors": []}
        output_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # PHASE 1: SEARCH
            await self._perform_search(from_date, to_date)
            total_count = await self._get_result_count()

            if total_count > 1000:
                raise TooManyResultsError(
                    f"Search returned {total_count} results. Halve date range."
                )

            logger.info("Found %d results. Starting collection...", total_count)

            # PHASE 2: PAGINATION & COLLECTION
            current_page = 1
            start_page = page_number

            # Navigate to start page if needed
            if start_page > 1:
                await self._go_to_page(start_page)
                current_page = start_page

            while len(records) < max_results:
                logger.info("Processing page %d...", current_page)
                debug_info["pages_visited"] += 1

                page_records = await self._process_page(output_dir)
                records.extend(page_records)

                if len(records) >= max_results:
                    break

                # Pagination
                next_btn = self.page.get_by_role("button", name="Next Page")
                if await next_btn.is_visible():
                    await next_btn.click()
                    await self.page.wait_for_load_state("networkidle")
                    current_page += 1
                else:
                    break  # No more pages

        except Exception as e:
            logger.error("Scrape failed: %s", e)
            debug_info["errors"].append(str(e))
            raise

        return records[:max_results], debug_info

    # ------------------------------------------------------------------
    # Step Implementations
    # ------------------------------------------------------------------

    async def _perform_search(self, start_date: str, end_date: str):
        """Fills search form and submits."""
        page = self.page
        await page.goto(self.BASE_URL)
        await page.wait_for_load_state("networkidle")

        # 3. Enter dummy search term (required to trigger search?)
        # Spec says: fill 'Internal Revenue Service'
        await page.get_by_label("Search by name or file number").fill(
            "Internal Revenue Service"
        )

        # 4. Open Advanced
        await page.get_by_role("button", name=re.compile(r"Advanced", re.I)).click()
        await page.get_by_label("File Type").wait_for(state="visible")

        # 5. Set File Type -> "Federal Tax Lien"
        # Note: Select by label text, not value
        await page.get_by_label("File Type").select_option(label="Federal Tax Lien")

        # 6. Set Dates
        await page.get_by_label("File Date: Start").fill(start_date)
        end_field = page.get_by_label("File Date: End")
        await end_field.fill(end_date)
        await end_field.press("Tab")

        # 7. Submit
        await page.get_by_role("button", name="Search").click()
        await page.wait_for_load_state("networkidle")

    async def _get_result_count(self) -> int:
        """Parses 'Results: X' text."""
        try:
            text = await self.page.locator("text=/Results: \\d+/").text_content()
            match = re.search(r"(\d+)", text)
            return int(match.group(1)) if match else 0
        except Exception:
            return 0

    async def _go_to_page(self, page_num: int):
        """Click specific page number button."""
        btn = self.page.get_by_role("button", name=str(page_num), exact=True)
        if await btn.is_visible():
            await btn.click()
            await self.page.wait_for_load_state("networkidle")
        else:
            logger.warning("Could not jump to page %d", page_num)

    async def _process_page(self, output_dir: str) -> List[LienRecord]:
        """Iterate rows on current page."""
        page = self.page
        records = []
        rows = page.locator("table tbody tr")
        count = await rows.count()

        for i in range(count):
            row = rows.nth(i)
            try:
                rec = await self._process_row(row, i, output_dir)
                if rec:
                    records.append(rec)
            except Exception as e:
                logger.warning("Row %d failed: %s", i, e)

        return records

    async def _process_row(
        self, row, row_index: int, output_dir: str
    ) -> Optional[LienRecord]:
        """Extract data from a single row + detail panel + history modal."""
        page = self.page

        # 11a. Read table cells
        cells = row.locator("td")
        # Format: [Type, Debtor, File#, Secured, Status, FilingDate, LapseDate]
        # (Indices may vary slightly based on actual column layout; assuming spec matches)
        ucc_type = (await cells.nth(0).text_content() or "").strip()
        debtor_info = (await cells.nth(1).text_content() or "").strip()
        file_number = (await cells.nth(2).text_content() or "").strip()
        _secured_raw = (await cells.nth(3).text_content() or "").strip()
        status = (await cells.nth(4).text_content() or "").strip()
        filing_date = (await cells.nth(5).text_content() or "").strip()
        lapse_date = (await cells.nth(6).text_content() or "").strip()

        # 11b. Open Detail Panel
        chevron = row.locator("button[aria-label], button:has(svg)").first
        await chevron.click()

        # Wait for panel (keyed by file number or general panel class)
        # Using a broad selector + file_number text filter
        panel_loc = page.locator(
            '[class*="detail"], [class*="panel"], [class*="side"]'
        ).filter(has_text=file_number)
        try:
            await panel_loc.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning("Detail panel failed to open for %s", file_number)
            return None

        # Helper to grab field values by label
        async def get_field(label: str) -> str:
            # "Label" <sibling> "Value"
            # Locates text=Label, then parent, then next sibling element's text
            try:
                return (
                    await page.locator(f"text={label}")
                    .locator("..")
                    .locator("+ *")
                    .text_content()
                    or ""
                ).strip()
            except Exception:
                return ""

        debtor_name = await get_field("Debtor Name")
        debtor_addr = await get_field("Debtor Address")
        sp_name = await get_field("Secured Party Name")
        sp_addr = await get_field("Secured Party Address")

        # 12. Open History Modal
        history_btn = page.get_by_role("button", name=re.compile(r"View History", re.I))
        if await history_btn.is_visible():
            await history_btn.click()
            modal = page.get_by_role("dialog", name="History")
            await modal.wait_for(state="visible", timeout=5000)

            # 13. Read history data (optional, can augment record)
            # doc_type = ...

            # 14. Download PDF
            download_link = modal.get_by_role("link", name=re.compile(r"Download", re.I))
            pdf_filename = ""
            if await download_link.is_visible():
                safe_date = re.sub(r"\D", "", filing_date)  # 01202026
                pdf_filename = f"{file_number}_{safe_date}.pdf"
                try:
                    async with page.expect_download(timeout=30000) as download_info:
                        await download_link.click()
                    download = await download_info.value
                    save_path = os.path.join(output_dir, pdf_filename)
                    await download.save_as(save_path)
                except Exception as e:
                    logger.warning("Download failed for %s: %s", file_number, e)
            else:
                logger.info("No download link for %s", file_number)

            # 15. Close History
            await modal.get_by_role("button", name=re.compile(r"close|×", re.I)).click()
            await modal.wait_for(state="hidden")

        # 16. Close Detail Panel
        close_btn = page.locator('[aria-label="Close"], button:has-text("×")').last
        if await close_btn.is_visible():
            await close_btn.click()

        # Build Record
        return LienRecord(
            ucc_type=ucc_type,
            debtor_name=debtor_name,
            debtor_address=debtor_addr,
            file_number=file_number,
            secured_party_name=sp_name,
            secured_party_address=sp_addr,
            status=status,
            filing_date=filing_date,
            lapse_date=lapse_date,
            document_type="Lien Financing Stmt",  # inferred/static for now
            pdf_filename=pdf_filename,
            processed=True,
        )
