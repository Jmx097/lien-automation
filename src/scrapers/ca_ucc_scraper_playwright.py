#!/usr/bin/env python3
"""
California SOS UCC Lien Scraper - Playwright Stealth Version
Uses Playwright with stealth plugins to bypass detection
"""

import asyncio
import os
import tempfile
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class LienRecord:
    site_id: str = "20"
    lien_or_receive_date: str = ""
    amount: str = ""
    lead_type: str = "Lien"
    lead_source: str = "777"
    liability_type: str = "IRS"
    business_personal: str = ""
    company: str = ""
    first_name: str = ""
    last_name: str = ""
    street: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    file_number: str = ""
    
    def to_dict(self):
        return {
            "Site Id": self.site_id,
            "LienOrReceiveDate": self.lien_or_receive_date,
            "Amount": self.amount,
            "LeadType": self.lead_type,
            "LeadSource": self.lead_source,
            "LiabilityType": self.liability_type,
            "BusinessPersonal": self.business_personal,
            "Company": self.company,
            "FirstName": self.first_name,
            "LastName": self.last_name,
            "Street": self.street,
            "City": self.city,
            "State": self.state,
            "Zip": self.zip_code,
            "FileNumber": self.file_number,
        }


class CAUCCScraper:
    BASE_URL = "https://bizfileonline.sos.ca.gov/search/ucc"
    
    def __init__(self, api_key=None):
        self.browser = None
        self.context = None
        self.page = None
        self.output_dir = os.getenv('OUTPUT_DIR', tempfile.gettempdir())
        
    async def __aenter__(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()
        
    async def init_browser(self):
        """Initialize browser with stealth settings"""
        # MUST be non-headless — Incapsula blocks headless Chromium
        headless = os.getenv('HEADLESS', 'false').lower() == 'true'
        slow_mo = int(os.getenv('SLOWMO', '0'))
        
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=browser_args
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/Los_Angeles',
        )
        
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = { runtime: {} };
        """)
        
        self.page = await self.context.new_page()
        self.page.on("console", lambda msg: logger.debug(f"Browser console: {msg.text}"))
        
    async def _save_artifact(self, name: str, content: str = None):
        """Save debug artifact (screenshot + optional HTML)."""
        try:
            ss = os.path.join(self.output_dir, f"{name}.png")
            await self.page.screenshot(path=ss, full_page=True)
            logger.debug(f"Screenshot → {ss}")
        except Exception as e:
            logger.debug(f"Screenshot failed: {e}")
        if content is not None:
            hp = os.path.join(self.output_dir, f"{name}.html")
            with open(hp, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.debug(f"HTML → {hp}")

    # ------------------------------------------------------------------
    # Core scraping flow
    # ------------------------------------------------------------------
    async def scrape_debug(self, from_date: str = None, to_date: str = None,
                           max_results: int = 50, page_number: int = 1
                           ) -> Tuple[List[LienRecord], List[str]]:
        """
        Full flow:
        1. Navigate to UCC search
        2. Click Advanced toggle
        3. Fill search + date range + record type
        4. Click Search (advanced-search-button)
        5. Wait for results (React SPA — no <table>; rows are divs)
        6. Parse visible rows
        7. Optionally paginate to page_number
        """
        if not from_date or not to_date:
            today = datetime.now()
            week_ago = today - timedelta(days=7)
            to_date = today.strftime("%m/%d/%Y")
            from_date = week_ago.strftime("%m/%d/%Y")
        
        log: List[str] = []
        records: List[LienRecord] = []

        def L(msg):
            log.append(msg)
            logger.info(msg)

        try:
            L(f"Date range: {from_date} → {to_date}  |  page={page_number}")
            await self.init_browser()

            # --- Step 1: Navigate ---
            L("➜ Navigating to UCC search …")
            await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(3)  # let Incapsula JS challenge resolve
            await self._save_artifact("01_loaded", await self.page.content())

            # --- Step 2: Click Advanced FIRST ---
            L("➜ Clicking Advanced toggle …")
            adv_btn = await self.page.wait_for_selector(
                'button.advanced-search-toggle', timeout=10000)
            if not adv_btn:
                raise RuntimeError("Advanced toggle not found — Incapsula may have blocked the page")
            await adv_btn.click()
            await asyncio.sleep(1)
            L("  ✓ Advanced panel open")

            # --- Step 3a: Fill search text ---
            L("➜ Filling search text …")
            search_input = await self.page.wait_for_selector(
                'input[placeholder*="Search by name"]', timeout=5000)
            if not search_input:
                # Fallback
                search_input = await self.page.query_selector('input[type="text"]')
            if not search_input:
                raise RuntimeError("Search input not found")
            await search_input.fill('Internal Revenue Service')
            L("  ✓ Search text filled")

            # --- Step 3b: Set Record Type to "Federal Tax Lien" ---
            L("➜ Setting Record Type …")
            try:
                select_el = await self.page.wait_for_selector(
                    '#field-RECORD_TYPE_ID', timeout=5000)
                await select_el.select_option(label='Federal Tax Lien')
                L("  ✓ Record type = Federal Tax Lien")
            except Exception as e:
                L(f"  ✗ Record type failed: {e}")

            # --- Step 3c: Fill date range ---
            L("➜ Filling date range …")
            try:
                ds = await self.page.wait_for_selector(
                    '#field-date-FILING_DATEs', timeout=5000)
                de = await self.page.wait_for_selector(
                    '#field-date-FILING_DATEe', timeout=5000)
                # Clear first, then type char-by-char (React controlled inputs)
                await ds.click(click_count=3)
                await ds.type(from_date, delay=50)
                await de.click(click_count=3)
                await de.type(to_date, delay=50)
                L(f"  ✓ Dates filled: {from_date} – {to_date}")
            except Exception as e:
                L(f"  ✗ Date fill failed: {e}")

            await self._save_artifact("02_form_filled", await self.page.content())

            # --- Step 4: Click the advanced-panel Search button ---
            L("➜ Clicking Search …")
            search_btn = await self.page.query_selector('button.advanced-search-button')
            if not search_btn:
                # Fallback
                search_btn = await self.page.query_selector('button:has-text("Search")')
            if not search_btn:
                raise RuntimeError("Search button not found")
            
            # Make sure button is enabled
            await asyncio.sleep(0.5)
            await search_btn.click()
            L("  ✓ Search clicked")

            # --- Step 5: Wait for results (React SPA) ---
            L("➜ Waiting for results …")
            # The SPA renders results as a list of anchor/div rows — not <table>.
            # Primary: wait for any .record-row, .search-result, or a link containing
            # "/detail/ucc" which is the detail page pattern.
            # Fallback: wait for the error message about >1000 results, or "no results".
            got_results = False
            try:
                await self.page.wait_for_selector(
                    'a[href*="/detail/"], .record-row, .search-result-item, '
                    '.results-list .result, [class*="result-row"]',
                    timeout=15000)
                got_results = True
                L("  ✓ Result rows detected")
            except Exception:
                L("  ! Primary result selector timed out — checking for error …")
                # Check for >1000 error
                error_el = await self.page.query_selector('h3:has-text("more than 1,000")')
                if error_el:
                    L("  ✗ ERROR: >1,000 results — narrow the date range")
                    await self._save_artifact("03_error", await self.page.content())
                    return [], log
                # Maybe just slow
                await asyncio.sleep(5)
                got_results = True  # try parsing anyway

            await self._save_artifact("03_results", await self.page.content())

            # Save final URL for verification
            final_url = self.page.url
            L(f"  URL: {final_url}")
            url_path = os.path.join(self.output_dir, "final_url.txt")
            with open(url_path, 'w') as f:
                f.write(final_url)

            if not got_results:
                L("No results to process.")
                return [], log

            # --- Step 5b: Paginate if needed ---
            if page_number > 1:
                L(f"➜ Paginating to page {page_number} …")
                for _ in range(page_number - 1):
                    next_btn = await self.page.query_selector(
                        'button:has-text("Next"), a:has-text("Next"), '
                        '[class*="next"], [aria-label="Next"]')
                    if next_btn:
                        await next_btn.click()
                        await asyncio.sleep(3)
                        L(f"  ✓ Clicked Next")
                    else:
                        L("  ✗ No Next button — already on last page")
                        break
                await self._save_artifact(f"03_page{page_number}", await self.page.content())

            # --- Step 6: Parse result rows ---
            L("➜ Parsing result rows …")
            html = await self.page.content()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Try multiple patterns to find result rows
            # Pattern A: <a href="/detail/ucc/...">
            detail_links = soup.find_all('a', href=lambda h: h and '/detail/' in h)
            L(f"  Detail links found: {len(detail_links)}")

            # Pattern B: rows with class containing 'record' or 'result'
            row_divs = soup.find_all('div', class_=lambda c: c and ('record' in str(c).lower() or 'result' in str(c).lower()))
            L(f"  Result divs found: {len(row_divs)}")

            # Pattern C: table rows (unlikely but fallback)
            table_rows = soup.find_all('tr')
            L(f"  Table rows found: {len(table_rows)}")

            # Use whatever pattern found results
            if detail_links:
                for i, link in enumerate(detail_links[:max_results]):
                    href = link.get('href', '')
                    text = link.get_text(strip=True)[:100]
                    L(f"  Row {i}: {text}  →  {href}")
                    record = LienRecord(file_number=href.split('/')[-1] if '/' in href else '')
                    records.append(record)
            elif row_divs:
                for i, div in enumerate(row_divs[:max_results]):
                    text = div.get_text(strip=True)[:100]
                    L(f"  Row {i}: {text}")
                    records.append(LienRecord())
            else:
                L("  ✗ No result rows found with any selector pattern")
                # Dump a broader DOM inventory for next debug iteration
                all_classes = set()
                for el in soup.find_all(True):
                    cls = el.get('class')
                    if cls:
                        all_classes.update(cls)
                interesting = [c for c in sorted(all_classes) if any(k in c.lower() for k in ['result', 'record', 'row', 'list', 'item', 'detail', 'lien'])]
                L(f"  Interesting CSS classes: {interesting[:20]}")

            # --- Step 7: Detail / History / Download (if rows found) ---
            if records and detail_links:
                L("➜ Opening first detail page for discovery …")
                first_link = detail_links[0]
                href = first_link.get('href', '')
                if href:
                    detail_url = href if href.startswith('http') else f"https://bizfileonline.sos.ca.gov{href}"
                    await self.page.goto(detail_url, wait_until='networkidle', timeout=15000)
                    await asyncio.sleep(2)
                    detail_html = await self.page.content()
                    await self._save_artifact("04_detail", detail_html)
                    L(f"  Detail URL: {self.page.url}")

                    # Update final_url.txt
                    with open(url_path, 'w') as f:
                        f.write(self.page.url)

                    # Look for "View History" button
                    history_btn = await self.page.query_selector(
                        'button:has-text("History"), a:has-text("History"), '
                        '[class*="history"]')
                    if history_btn:
                        L("  ✓ Found History button — clicking …")
                        await history_btn.click()
                        await asyncio.sleep(2)
                        await self._save_artifact("05_history", await self.page.content())
                        L(f"  History URL: {self.page.url}")

                        # Look for download link
                        download_link = await self.page.query_selector(
                            'a:has-text("Download"), button:has-text("Download"), '
                            'a[href*=".pdf"], a[href*="download"]')
                        if download_link:
                            dl_href = await download_link.get_attribute('href') or ''
                            L(f"  ✓ Download link found: {dl_href}")
                        else:
                            L("  ✗ No download link found on History page")
                    else:
                        L("  ✗ No History button found on detail page")
                        # Dump buttons for debugging
                        btns = await self.page.query_selector_all('button, a')
                        btn_texts = []
                        for b in btns[:20]:
                            t = await b.text_content()
                            btn_texts.append(t.strip()[:40] if t else '')
                        L(f"  Buttons on detail page: {btn_texts}")

            L(f"✓ Done. {len(records)} records found.")
            return records, log
            
        except Exception as e:
            log.append(f"ERROR: {str(e)}")
            import traceback
            log.append(traceback.format_exc()[:500])
            try:
                await self._save_artifact("error", await self.page.content())
            except:
                pass
            return records, log
        
    async def scrape(self, from_date: str = None, to_date: str = None,
                     max_results: int = 50) -> List[LienRecord]:
        """Main scraping method"""
        records, _ = await self.scrape_debug(from_date, to_date, max_results)
        return records
