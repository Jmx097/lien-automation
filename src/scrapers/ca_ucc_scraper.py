#!/usr/bin/env python3
"""
California SOS UCC Lien Scraper
Scrapes IRS tax liens from CA Secretary of State UCC database
"""

import asyncio
import re
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import json

from playwright.async_api import async_playwright, Page, Browser
import pytesseract
from pdf2image import convert_from_path
import tempfile
import os


@dataclass
class LienRecord:
    site_id: str = "11"  # CA UCC Site
    lien_or_receive_date: str = ""
    amount: str = ""
    lead_type: str = "Lien"  # Notice of Federal Tax Lien
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
            "Zip": self.zip_code
        }


class CAUCCScraper:
    BASE_URL = "https://bizfileonline.sos.ca.gov/search/ucc"
    
    def __init__(self, headless: bool = True, delay_range: tuple = (2, 5)):
        self.headless = headless
        self.delay_range = delay_range  # Random delay between requests
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.results: List[LienRecord] = []
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = await context.new_page()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()
        
    async def random_delay(self):
        """Random delay to be respectful to the server"""
        delay = random.uniform(*self.delay_range)
        await asyncio.sleep(delay)
        
    async def navigate_to_search(self):
        """Navigate to UCC search page"""
        print(f"Navigating to {self.BASE_URL}")
        await self.page.goto(self.BASE_URL)
        await self.page.wait_for_load_state("networkidle")
        await self.random_delay()
        
    async def click_advanced_search(self):
        """Click Advanced search link"""
        print("Clicking Advanced search...")
        try:
            # Use get_by_role for more reliable selection
            advanced_button = self.page.get_by_role("button", name="Advanced")
            if await advanced_button.is_visible():
                await advanced_button.click()
                await self.random_delay()
                print("Advanced search opened")
            else:
                print("Advanced button not visible")
        except Exception as e:
            print(f"Note: Could not click Advanced: {e}")
            
    async def fill_search_criteria(self, from_date: str, to_date: str):
        """
        Fill in search criteria
        from_date/to_date format: MM/DD/YYYY
        """
        print(f"Filling search criteria: IRS, {from_date} to {to_date}")
        
        # Wait a moment for advanced panel to open
        await asyncio.sleep(2)
        
        # Fill "Internal Revenue Service" in party field
        try:
            # Try to find by placeholder or label
            party_field = self.page.get_by_placeholder("Name", exact=False)
            if await party_field.count() > 0:
                await party_field.first.fill("Internal Revenue Service")
                print("Filled party field with 'Internal Revenue Service'")
            else:
                # Try any visible text input
                inputs = await self.page.locator("input[type=text]").all()
                for inp in inputs:
                    if await inp.is_visible():
                        await inp.fill("Internal Revenue Service")
                        print("Filled first visible text input with 'Internal Revenue Service'")
                        break
                    
        except Exception as e:
            print(f"Warning: Could not fill party field: {e}")
            
        # Fill date range
        try:
            # Look for date inputs by type
            date_inputs = await self.page.locator("input[type=date]").all()
            if len(date_inputs) >= 2:
                # Convert MM/DD/YYYY to YYYY-MM-DD for HTML date inputs
                from_parts = from_date.split("/")
                to_parts = to_date.split("/")
                from_iso = f"{from_parts[2]}-{from_parts[0]}-{from_parts[1]}"
                to_iso = f"{to_parts[2]}-{to_parts[0]}-{to_parts[1]}"
                
                await date_inputs[0].fill(from_iso)
                await date_inputs[1].fill(to_iso)
                print(f"Filled date range: {from_date} to {to_date}")
            else:
                print("Warning: Could not find date range fields")
                
        except Exception as e:
            print(f"Warning: Could not fill date fields: {e}")
            
        await self.random_delay()
        
    async def submit_search(self):
        """Submit the search form"""
        print("Submitting search...")
        try:
            # Try to find search button by role
            search_button = self.page.get_by_role("button", name="Search")
            if await search_button.count() > 0 and await search_button.first.is_visible():
                await search_button.first.click()
                print("Search submitted")
            else:
                # Try pressing Enter on the first input
                await self.page.locator("input").first.press("Enter")
                print("Search submitted (Enter key)")
                
        except Exception as e:
            print(f"Warning: Could not submit search: {e}")
            
        # Wait for results to load
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(5)  # Give time for results to render
        
    async def get_results_count(self) -> int:
        """Get number of search results"""
        try:
            # Look for results count indicator
            count_text = await self.page.locator("text=/\\d+ result/i").first.inner_text()
            match = re.search(r'(\d+)', count_text)
            if match:
                return int(match.group(1))
        except:
            pass
        return 0
        
    async def process_results(self, max_results: int = 50) -> List[LienRecord]:
        """
        Process search results
        Only extract "Notice of Federal Tax Lien" entries
        """
        print(f"Processing up to {max_results} results...")
        records = []
        
        try:
            # Find all result rows
            result_rows = await self.page.locator("tr, .result-row, [class*=result]").all()
            print(f"Found {len(result_rows)} result rows")
            
            for i, row in enumerate(result_rows[:max_results]):
                try:
                    # Check if this is a "Notice of Federal Tax Lien"
                    row_text = await row.inner_text()
                    
                    if "Notice of Federal Tax Lien" not in row_text:
                        continue  # Skip non-lien entries
                        
                    print(f"\nProcessing result {i+1}: Notice of Federal Tax Lien")
                    
                    # Extract filing date from row if available
                    filing_date = self._extract_date_from_row(row_text)
                    
                    # Click on the result to view details
                    await row.click()
                    await self.random_delay()
                    await asyncio.sleep(2)
                    
                    # Click "View history"
                    view_history = await self.page.locator("text=View history").first
                    if await view_history.is_visible():
                        await view_history.click()
                        await self.random_delay()
                        await asyncio.sleep(2)
                        
                    # Download document
                    download_link = await self.page.locator("text=Download").first
                    if await download_link.is_visible():
                        # Trigger download
                        async with self.page.expect_download() as download_info:
                            await download_link.click()
                        download = await download_info.value
                        
                        # Save to temp file
                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                            pdf_path = tmp.name
                            await download.save_as(pdf_path)
                            
                        print(f"Downloaded PDF: {pdf_path}")
                        
                        # Extract data from PDF
                        record = await self._extract_from_pdf(pdf_path, filing_date)
                        records.append(record)
                        
                        # Clean up
                        os.unlink(pdf_path)
                        
                    # Go back to results
                    await self.page.go_back()
                    await self.page.go_back()
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    print(f"Error processing result {i+1}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error processing results: {e}")
            
        print(f"\nProcessed {len(records)} lien records")
        return records
        
    def _extract_date_from_row(self, row_text: str) -> str:
        """Extract filing date from result row text"""
        # Look for date patterns MM/DD/YYYY or MM-DD-YYYY
        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        match = re.search(date_pattern, row_text)
        if match:
            return match.group(1)
        return ""
        
    async def _extract_from_pdf(self, pdf_path: str, filing_date: str) -> LienRecord:
        """
        Extract data from PDF using OCR
        This is a placeholder - actual implementation would use PDF parsing
        """
        record = LienRecord()
        record.lien_or_receive_date = filing_date
        
        try:
            # Convert PDF to images for OCR
            images = convert_from_path(pdf_path)
            
            full_text = ""
            for image in images:
                text = pytesseract.image_to_string(image)
                full_text += text + "\n"
                
            print(f"Extracted text from PDF (first 500 chars):\n{full_text[:500]}")
            
            # Parse the extracted text
            record = self._parse_lien_text(full_text, filing_date)
            
        except Exception as e:
            print(f"Error extracting from PDF: {e}")
            
        return record
        
    def _parse_lien_text(self, text: str, filing_date: str) -> LienRecord:
        """
        Parse extracted text and map to LienRecord fields
        Based on the mapping guide rules
        """
        record = LienRecord()
        record.lien_or_receive_date = filing_date
        record.lead_type = "Lien"
        record.lead_source = "777"
        record.liability_type = "IRS"
        
        # Extract Amount (look for "Total" followed by number)
        amount_match = re.search(r'Total[:\s]*\$?([\d,]+)', text, re.IGNORECASE)
        if amount_match:
            record.amount = amount_match.group(1).replace(',', '')
            
        # Extract taxpayer name and determine Business vs Personal
        taxpayer_section = re.search(r'Name of Taxpayer[:\s]*([^\n]+)', text, re.IGNORECASE)
        if taxpayer_section:
            taxpayer_name = taxpayer_section.group(1).strip()
            record = self._classify_taxpayer(taxpayer_name, record)
            
        # Extract address
        address_match = re.search(r'(?:Address|Residence)[:\s]*([^\n,]+),\s*([^\n,]+),\s*(\w{2})\s*(\d{5})', text, re.IGNORECASE)
        if address_match:
            record.street = address_match.group(1).strip()
            record.city = address_match.group(2).strip()
            record.state = address_match.group(3)
            record.zip_code = address_match.group(4)
            
        return record
        
    def _classify_taxpayer(self, name: str, record: LienRecord) -> LienRecord:
        """
        Classify taxpayer as Business or Personal based on mapping guide rules
        """
        name_upper = name.upper()
        
        # Business indicators
        business_keywords = ['INC', 'LLC', 'CORP', 'CORPORATION', 'COMPANY', 
                           'CO.', 'LTD', 'LIMITED', 'SERVICE', 'SOLUTIONS',
                           'BUSINESS', 'ENTERPRISE', 'ENTERPRISES', 'GROUP',
                           'PARTNERSHIP', 'LP', 'LLP', 'HOLDINGS', 'ASSOCIATES']
        
        # Check for business keywords
        is_business = any(keyword in name_upper for keyword in business_keywords)
        
        # Check for personal name pattern (First Last or First M Last)
        name_parts = name.split()
        looks_like_person = len(name_parts) >= 2 and len(name_parts) <= 4
        
        # Check if it looks like a person's name (no business keywords)
        if is_business or not looks_like_person:
            record.business_personal = "Business"
            record.company = name
        else:
            record.business_personal = "Personal"
            record.first_name = name_parts[0]
            record.last_name = name_parts[-1]
            if len(name_parts) == 3:
                # Could be First Middle Last - use middle as part of first or skip
                pass
                
        return record
        
    async def scrape(self, from_date: str, to_date: str, max_results: int = 50) -> List[LienRecord]:
        """
        Main scraping method
        
        Args:
            from_date: Start date (MM/DD/YYYY)
            to_date: End date (MM/DD/YYYY)
            max_results: Maximum number of results to process
            
        Returns:
            List of LienRecord objects
        """
        print(f"\n{'='*60}")
        print(f"CA UCC Lien Scraper")
        print(f"Date Range: {from_date} to {to_date}")
        print(f"Max Results: {max_results}")
        print(f"{'='*60}\n")
        
        try:
            await self.navigate_to_search()
            await self.click_advanced_search()
            await self.fill_search_criteria(from_date, to_date)
            await self.submit_search()
            
            results = await self.process_results(max_results)
            return results
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            return []
            

async def main():
    """Example usage"""
    # Calculate date range (last 30 days)
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)
    
    from_date_str = from_date.strftime("%m/%d/%Y")
    to_date_str = to_date.strftime("%m/%d/%Y")
    
    async with CAUCCScraper(headless=True) as scraper:
        records = await scraper.scrape(
            from_date=from_date_str,
            to_date=to_date_str,
            max_results=10
        )
        
        # Print results
        print(f"\n{'='*60}")
        print(f"SCRAPING COMPLETE")
        print(f"Records found: {len(records)}")
        print(f"{'='*60}\n")
        
        for i, record in enumerate(records, 1):
            print(f"\nRecord {i}:")
            for key, value in record.to_dict().items():
                print(f"  {key}: {value}")
                
        # Save to JSON
        output_file = f"ca_ucc_liens_{from_date_str.replace('/', '-')}_{to_date_str.replace('/', '-')}.json"
        with open(output_file, 'w') as f:
            json.dump([r.to_dict() for r in records], f, indent=2)
        print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
