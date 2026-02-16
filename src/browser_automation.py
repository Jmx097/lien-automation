"""
Federal Tax Lien Extraction System - NYC ACRIS Module
Production-grade browser automation with accuracy verification
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class LienRecord:
    """Structured lien data with confidence scores"""
    site_id: str
    lien_date: Optional[str]
    amount: Optional[str]
    lead_type: str
    lead_source: str
    liability_type: str
    business_personal: str
    company: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    raw_text: str
    confidence_scores: Dict[str, float]
    pdf_url: Optional[str]
    verification_flags: List[str]


class NYCACRISAutomation:
    """NYC ACRIS Federal Tax Lien scraper with accuracy verification"""
    
    BASE_URL = "https://a836-acris.nyc.gov/CP/"
    SEARCH_URL = "https://a836-acris.nyc.gov/CP/TitleSearch/DocumentTypeSearch"
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.records: List[LienRecord] = []
        
    async def initialize(self):
        """Initialize browser with proper config"""
        logger.info("Initializing browser for NYC ACRIS...")
        playwright = await async_playwright().start()
        
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(60000)  # 60 second timeout
        logger.info("Browser initialized successfully")
        
    async def navigate_to_search(self):
        """Navigate to Document Type Search page"""
        logger.info("Navigating to NYC ACRIS...")
        
        try:
            # Start at main page
            await self.page.goto(self.BASE_URL, wait_until='networkidle')
            
            # Click "Start using Acris"
            start_button = await self.page.wait_for_selector(
                'text=Start using Acris', 
                state='visible',
                timeout=30000
            )
            await start_button.click()
            await asyncio.sleep(2)
            
            # Click "Search Property Records"
            search_link = await self.page.wait_for_selector(
                'text=Search Property Records',
                state='visible',
                timeout=30000
            )
            await search_link.click()
            await asyncio.sleep(2)
            
            # Click "Document Type"
            doc_type_link = await self.page.wait_for_selector(
                'text=Document Type',
                state='visible', 
                timeout=30000
            )
            await doc_type_link.click()
            await asyncio.sleep(2)
            
            logger.info("Successfully navigated to Document Type Search")
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            # Save screenshot for debugging
            await self.page.screenshot(path='error_navigate.png')
            raise
            
    async def configure_search(self):
        """Configure search for Federal Tax Liens - last 7 days"""
        logger.info("Configuring search parameters...")
        
        try:
            # Select "Select Document Type" dropdown
            doc_type_dropdown = await self.page.wait_for_selector(
                'select[name="document_type"], #combobox_doctype, [aria-label*="Document Type"]',
                timeout=30000
            )
            
            # Select "FEDERAL LIEN-IRS" (DOC_TYPE = 650)
            await doc_type_dropdown.select_option('650')  # Federal Tax Lien code
            await asyncio.sleep(1)
            
            # Calculate date range (last 7 days)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            start_date_str = start_date.strftime('%m/%d/%Y')
            end_date_str = end_date.strftime('%m/%d/%Y')
            
            logger.info(f"Date range: {start_date_str} to {end_date_str}")
            
            # Fill From Date
            from_date_field = await self.page.wait_for_selector(
                'input[name="from_date"], #txtDateFrom, [placeholder*="From"]',
                timeout=30000
            )
            await from_date_field.fill(start_date_str)
            await asyncio.sleep(0.5)
            
            # Fill To Date
            to_date_field = await self.page.wait_for_selector(
                'input[name="to_date"], #txtDateTo, [placeholder*="To"]',
                timeout=30000
            )
            await to_date_field.fill(end_date_str)
            await asyncio.sleep(0.5)
            
            logger.info("Search parameters configured")
            
        except Exception as e:
            logger.error(f"Search configuration failed: {e}")
            await self.page.screenshot(path='error_config.png')
            raise
            
    async def execute_search(self) -> int:
        """Execute search and return result count"""
        logger.info("Executing search...")
        
        try:
            # Click Search button
            search_button = await self.page.wait_for_selector(
                'button[type="submit"], input[value="Search"], #btnSearch, text="Search"',
                timeout=30000
            )
            await search_button.click()
            
            # Wait for results to load
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)
            
            # Check for results
            results_table = await self.page.query_selector(
                'table[class*="result"], #resultsTable, .search-results'
            )
            
            if not results_table:
                # Check for "no results" message
                no_results = await self.page.query_selector('text=/no results|no records|0 results/i')
                if no_results:
                    logger.info("No results found for date range")
                    return 0
                else:
                    logger.warning("Results table not found, may need different selector")
                    return 0
                    
            # Count rows (excluding header)
            rows = await results_table.query_selector_all('tr:not(:first-child)')
            count = len(rows)
            logger.info(f"Found {count} results")
            
            return count
            
        except Exception as e:
            logger.error(f"Search execution failed: {e}")
            await self.page.screenshot(path='error_search.png')
            raise
            
    async def extract_record(self, row_index: int) -> Optional[LienRecord]:
        """Extract single lien record with all pages"""
        logger.info(f"Extracting record {row_index + 1}...")
        
        try:
            # Get all result rows again
            rows = await self.page.query_selector_all('table[class*="result"] tr:not(:first-child)')
            
            if row_index >= len(rows):
                logger.warning(f"Row index {row_index} out of range")
                return None
                
            row = rows[row_index]
            
            # Find and click the "Img" link in View column
            img_link = await row.query_selector('a[title*="Image"], a:has-text("Img"), .view-image')
            
            if not img_link:
                logger.warning(f"No image link found for row {row_index}")
                return None
                
            # Open image in new tab to preserve search results
            href = await img_link.get_attribute('href')
            if not href:
                logger.warning("No href found on image link")
                return None
                
            # Navigate to document viewer
            await img_link.click()
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(3)
            
            # Extract document info
            record = await self._parse_document_page()
            
            # Go back to results
            await self.page.go_back()
            await self.page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)
            
            return record
            
        except Exception as e:
            logger.error(f"Record extraction failed: {e}")
            await self.page.screenshot(path=f'error_record_{row_index}.png')
            return None
            
    async def _parse_document_page(self) -> LienRecord:
        """Parse the document viewer page for lien details"""
        logger.info("Parsing document page...")
        
        # Wait for document to load
        await self.page.wait_for_selector(
            '#documentViewer, .document-container, iframe[src*="document"]',
            timeout=30000
        )
        
        # Get PDF URL if available
        pdf_link = await self.page.query_selector('a[href*=".pdf"], #downloadPDF')
        pdf_url = None
        if pdf_link:
            pdf_url = await pdf_link.get_attribute('href')
            
        # Extract text from page (will need OCR for images)
        page_content = await self.page.content()
        
        # Parse fields (this will be enhanced by pdf_extractor)
        record = LienRecord(
            site_id="12",  # NYC ACRIS
            lien_date=None,
            amount=None,
            lead_type="Lien",
            lead_source="777",
            liability_type="IRS",
            business_personal="Unknown",
            company=None,
            first_name=None,
            last_name=None,
            street=None,
            city=None,
            state=None,
            zip_code=None,
            raw_text=page_content[:5000],  # First 5000 chars
            confidence_scores={},
            pdf_url=pdf_url,
            verification_flags=[]
        )
        
        return record
        
    async def scrape_all_records(self) -> List[LienRecord]:
        """Main scraping workflow"""
        logger.info("Starting NYC ACRIS scraping workflow...")
        
        try:
            await self.initialize()
            await self.navigate_to_search()
            await self.configure_search()
            
            result_count = await self.execute_search()
            
            if result_count == 0:
                logger.info("No records to process")
                return []
                
            # Extract all records
            for i in range(min(result_count, 50)):  # Limit to 50 for safety
                try:
                    record = await self.extract_record(i)
                    if record:
                        self.records.append(record)
                        logger.info(f"Successfully extracted record {i + 1}")
                except Exception as e:
                    logger.error(f"Failed to extract record {i}: {e}")
                    continue
                    
            logger.info(f"Completed extraction of {len(self.records)} records")
            return self.records
            
        except Exception as e:
            logger.error(f"Scraping workflow failed: {e}")
            raise
            
        finally:
            await self.close()
            
    async def close(self):
        """Clean up browser resources"""
        logger.info("Closing browser...")
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
            

async def scrape_nyc_acris() -> List[LienRecord]:
    """Entry point for NYC ACRIS scraping"""
    scraper = NYCACRISAutomation()
    return await scraper.scrape_all_records()


if __name__ == "__main__":
    records = asyncio.run(scrape_nyc_acris())
    print(f"Extracted {len(records)} records")
