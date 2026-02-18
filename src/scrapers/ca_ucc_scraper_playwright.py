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
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = await self.browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
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
        print(f"DEBUG: _perform_search START: {start_date} to {end_date}")
        page = self.page
        await page.goto(self.BASE_URL)
        print("DEBUG: Navigated to URL")
        await page.wait_for_load_state("networkidle")
        print("DEBUG: Page loaded")

        # 3. Enter dummy search term (required to trigger search?)
        # Use precise placeholder selector or ID if available (from debug script analysis)
        # Spec says: fill 'Internal Revenue Service'
        await page.get_by_role("textbox", name="Search by name or file number").fill(
            "Internal Revenue Service"
        )
        print("DEBUG: Filled search term")

        # 4. Open Advanced
        await page.get_by_role("button", name=re.compile(r"Advanced", re.I)).click()
        print("DEBUG: Clicked Advanced")
        # Wait for File Type dropdown by ID
        await page.locator("#field-RECORD_TYPE_ID").wait_for(state="visible")
        print("DEBUG: File Type visible")

        # 5. Set File Type -> "Federal Tax Lien"
        await page.locator("#field-RECORD_TYPE_ID").select_option(label="Federal Tax Lien")
        print("DEBUG: Selected File Type")

        # 6. Set Dates using IDs found in DOM analysis
        # Start Date
        await page.locator("#field-date-FILING_DATEs").fill(start_date)
        print("DEBUG: Filled Start Date")
        
        # End Date
        await page.locator("#field-date-FILING_DATEe").fill(end_date)
        await page.locator("#field-date-FILING_DATEe").press("Tab")
        print("DEBUG: Filled End Date")

        # 7. Submit
        await page.get_by_role("button", name="Search").click()
        print("DEBUG: Clicked Search")
        await page.wait_for_load_state("networkidle")
        print("DEBUG: Search results likely loaded")

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
        """Extract data from a single row + detail panel + history modal (Step 7)."""
        page = self.page
        print(f"DEBUG: Processing row {row_index}")

        # 7a. READ ROW DATA
        cells = row.locator("td")
        if await cells.count() < 7:
            print(f"DEBUG: Row {row_index} has insufficient cells")
            return None

        ucc_type = (await cells.nth(0).text_content() or "").strip()
        debtor_info = (await cells.nth(1).text_content() or "").strip()
        file_number = (await cells.nth(2).text_content() or "").strip()
        # secured_party_raw = await cells.nth(3).text_content()
        status = (await cells.nth(4).text_content() or "").strip()
        filing_date_row = (await cells.nth(5).text_content() or "").strip()
        lapse_date = (await cells.nth(6).text_content() or "").strip()

        # 7b. OPEN DETAIL PANEL: Click the row (or first cell)
        # Spec says "Click the row". Some UIs require clicking specific cell to avoid other actions.
        # Safest is usually the first text cell.
        try:
            await cells.first.click()
        except Exception:
            # Fallback to row click
            await row.click()

        # Wait for panel
        panel_loc = page.locator('[class*="detail"], [class*="panel"], [class*="side"]').filter(has_text=file_number).first
        try:
            await panel_loc.wait_for(state="visible", timeout=5000)
        except PlaywrightTimeoutError:
            print(f"DEBUG: Detail panel failed for {file_number}")
            return None # Log as "panel_failed" implicitly by returning None

        # Read Panel Fields
        async def get_field(label: str) -> str:
            try:
                # Text=Label -> Parent -> Sibling
                return (await page.locator(f"text={label}").locator("..").locator("+ *").text_content() or "").strip()
            except:
                return ""

        debtor_name = await get_field("Debtor Name")
        debtor_addr = await get_field("Debtor Address")
        sp_name = await get_field("Secured Party Name")
        sp_addr = await get_field("Secured Party Address")

        # 7c. VIEW HISTORY (Clock Icon)
        # Look for button with "History" in aria-label or text, or icon.
        history_btn = page.get_by_role("button", name=re.compile(r"History|View History", re.I))
        # If strict mode fails, try .first or specific selector
        if await history_btn.count() > 1:
            history_btn = history_btn.first
        
        pdf_filename = ""
        doc_type = "Lien Financing Stmt" # Default
        filing_date = filing_date_row 

        if await history_btn.is_visible():
            await history_btn.click()
            modal = page.get_by_role("dialog") # , name="History" might be flaky if title is inside
            try:
                await modal.wait_for(state="visible", timeout=5000)
                
                # 7d. READ HISTORY RECORD
                # Extract Doc Type / Date if possible from modal table?
                # Spec: "Read: Document Type, File Number, Date"
                # Assuming first row of history table in modal
                history_rows = modal.locator("table tbody tr")
                if await history_rows.count() > 0:
                    first_hist = history_rows.first
                    # Columns unknown, assuming standard layout or taking from spec example
                    # Spec doesn't give column indices. We'll rely on row data for dates mostly.
                    pass

                # 7e. DOWNLOAD
                download_link = modal.get_by_role("link", name=re.compile(r"Download|Image", re.I))
                if await download_link.is_visible():
                    safe_date = re.sub(r"\D", "", filing_date_row)
                    pdf_filename = f"{file_number}_{safe_date}.pdf"
                    
                    try:
                        async with page.expect_download(timeout=15000) as download_info:
                            await download_link.first.click()
                        download = await download_info.value
                        save_path = os.path.join(output_dir, pdf_filename)
                        await download.save_as(save_path)
                        print(f"DEBUG: Downloaded {pdf_filename}")
                    except Exception as e:
                        print(f"DEBUG: Download failed {file_number}: {e}")
                else:
                    print(f"DEBUG: No download link for {file_number}")

                # 7f. CLOSE HISTORY MODAL
                close_hist = modal.get_by_role("button", name=re.compile(r"close|×", re.I))
                if await close_hist.is_visible():
                    await close_hist.click()
                await modal.wait_for(state="hidden")

            except Exception as e:
                print(f"DEBUG: History modal error {file_number}: {e}")
                # Try to close modal if stuck?
                await page.keyboard.press("Escape")

        # 7g. CLOSE DETAIL PANEL
        close_panel = page.locator('[aria-label="Close"], button:has-text("×")').last
        if await close_panel.is_visible():
             await close_panel.click()

        # Build Record
        return LienRecord(
            ucc_type=ucc_type,
            debtor_name=debtor_name or debtor_info, # Fallback
            debtor_address=debtor_addr,
            file_number=file_number,
            secured_party_name=sp_name,
            secured_party_address=sp_addr,
            status=status,
            filing_date=filing_date,
            lapse_date=lapse_date,
            document_type=doc_type,
            pdf_filename=pdf_filename,
            processed=True,
        )
