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
    
    def __init__(self, api_key=None):
        # api_key parameter accepted for compatibility but not used
        self.browser = None
        self.context = None
        self.page = None
        # Use temp dir for artifacts, compatible with Windows/Linux
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
        from playwright.async_api import async_playwright
        
        # Check env vars for debug settings
        headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        slow_mo = int(os.getenv('SLOWMO', '0'))
        
        # Launch browser with args to avoid detection
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
        
        # Create context with realistic viewport and user agent
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='en-US',
            timezone_id='America/Los_Angeles',
        )
        
        # Add stealth scripts
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
        
        # Add logging for console messages
        self.page.on("console", lambda msg: logger.debug(f"Browser console: {msg.text}"))
        
    async def scrape_debug(self, from_date: str = None, to_date: str = None, max_results: int = 50) -> Tuple[List[LienRecord], List[str]]:
        """Scrape with debug info"""
        if not from_date or not to_date:
            today = datetime.now()
            three_months_ago = today - timedelta(days=90)
            to_date = today.strftime("%m/%d/%Y")
            from_date = three_months_ago.strftime("%m/%d/%Y")
        
        debug_info = []
        debug_info.append(f"Date Range: {from_date} to {to_date}")
        debug_info.append(f"Output Directory: {self.output_dir}")
        
        try:
            debug_info.append("Initializing Playwright with stealth...")
            await self.init_browser()
            
            debug_info.append(f"Navigating to: {self.BASE_URL}")
            await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=30000)
            
            # Wait a moment for any JS challenges to complete
            await asyncio.sleep(3)
            
            # Get page info
            title = await self.page.title()
            debug_info.append(f"Page title: {title}")
            
            url = self.page.url
            debug_info.append(f"Current URL: {url}")
            
            # Get HTML content
            html = await self.page.content()
            debug_info.append(f"HTML length: {len(html)} bytes")
            debug_info.append(f"HTML first 500: {html[:500]}...")
            
            # Take screenshot for debugging
            try:
                screenshot_path = os.path.join(self.output_dir, "ca_sos_screenshot.png")
                await self.page.screenshot(path=screenshot_path, full_page=True)
                debug_info.append(f"✓ Screenshot saved to {screenshot_path}")
            except Exception as screenshot_error:
                debug_info.append(f"Screenshot failed: {str(screenshot_error)}")
            
            # Look for iframes
            iframes = await self.page.query_selector_all('iframe')
            debug_info.append(f"Iframes found: {len(iframes)}")
            
            for i, iframe in enumerate(iframes[:3]):
                src = await iframe.get_attribute('src') or 'N/A'
                debug_info.append(f"  Iframe {i}: {src[:100]}")
            
            # Try to find and fill the search form
            try:
                debug_info.append("Looking for search form...")
                
                # Wait for form elements
                await self.page.wait_for_selector('input[type="text"]', timeout=10000)
                
                # Find the search input (usually first text input)
                search_input = await self.page.query_selector('input[type="text"]')
                if search_input:
                    debug_info.append("Found search input, filling...")
                    try:
                        await search_input.fill('Internal Revenue Service')
                        debug_info.append("✓ Search input filled")
                    except Exception as fill_error:
                        debug_info.append(f"✗ Failed to fill search input: {str(fill_error)}")
                        return [], debug_info
                    
                    # Click Advanced Search
                    try:
                        debug_info.append("Looking for Advanced Search toggle...")
                        advanced_btn = await self.page.wait_for_selector('button.advanced-search-toggle, button:has-text("Advanced")', timeout=5000)
                        if advanced_btn:
                            await advanced_btn.click()
                            debug_info.append("✓ Clicked Advanced Search")
                            await asyncio.sleep(1)
                            # Look for Date Fields
                            # Identified via parse_html.py: field-date-FILING_DATEs, field-date-FILING_DATEe
                            try:
                                await self.page.fill('#field-date-FILING_DATEs', from_date)
                                await self.page.fill('#field-date-FILING_DATEe', to_date)
                                debug_info.append(f"✓ Filled filing dates: {from_date} - {to_date}")
                            except Exception as date_error:
                                 debug_info.append(f"✗ Failed to fill dates: {date_error}")

                            # Look for Document Type checkbox/filter
                            # Identified via parse_html.py: select#field-RECORD_TYPE_ID
                            try:
                                # Select 'Federal Tax Lien'
                                select_elem = await self.page.query_selector('#field-RECORD_TYPE_ID')
                                if select_elem:
                                    # Iterate options to find exact match if needed, or just try selecting by label
                                    await select_elem.select_option(label='Federal Tax Lien')
                                    debug_info.append("✓ Selected 'Federal Tax Lien'")
                                else:
                                    debug_info.append("✗ Could not find Record Type select")
                            except Exception as e:
                                debug_info.append(f"Filter selection error: {e}")
                                
                    except Exception as adv_error:
                        debug_info.append(f"Advanced search interaction failed: {str(adv_error)}")
                    
                    # Find and click submit
                    debug_info.append("Looking for submit button...")
                    
                    # Try various selectors for the search button
                    # Identified via parse_html.py: button.advanced-search-button
                    selectors = [
                        'button.advanced-search-button',
                        'button[type="submit"]',
                        'button:has-text("Search")',
                        'button[class*="search"]',
                        'button',
                    ]
                    
                    submit_btn = None
                    for selector in selectors:
                        submit_btn = await self.page.query_selector(selector)
                        if submit_btn:
                            debug_info.append(f"Found submit button with selector: {selector}")
                            break
                    
                    debug_info.append(f"Submit button found: {submit_btn is not None}")
                    
                    if submit_btn:
                        debug_info.append("Clicking submit button...")
                        try:
                            # Wait for button to be enabled
                            debug_info.append("Waiting for button to be enabled...")
                            await asyncio.sleep(2)
                            
                            # Check if button is enabled
                            is_enabled = await submit_btn.is_enabled()
                            debug_info.append(f"Button enabled: {is_enabled}")
                            
                            if not is_enabled:
                                debug_info.append("Button still disabled, trying Enter key...")
                                # Press Tab then Enter to trigger form validation
                                await search_input.press('Tab')
                                await asyncio.sleep(1)
                                await self.page.keyboard.press('Enter')
                                debug_info.append("✓ Enter key pressed")
                            else:
                                await submit_btn.click()
                                debug_info.append("✓ Submit button clicked")
                        except Exception as click_error:
                            debug_info.append(f"✗ Submit click failed: {str(click_error)}")
                            return [], debug_info
                        
                        # Wait for results to load
                        debug_info.append("Waiting 8 seconds for results...")
                        await asyncio.sleep(8)
                        
                        # Check for results
                        html = await self.page.content()
                        debug_info.append(f"After search - HTML length: {len(html)} bytes")
                        
                        # Save HTML for debugging
                        try:
                            html_path = os.path.join(self.output_dir, "ca_sos_results.html")
                            with open(html_path, 'w', encoding='utf-8') as f:
                                f.write(html)
                            debug_info.append(f"✓ HTML saved to {html_path}")
                        except Exception as save_error:
                            debug_info.append(f"Could not save HTML: {str(save_error)}")
                        
                        # Get new URL
                        new_url = self.page.url
                        debug_info.append(f"URL after search: {new_url}")
                        
                        # Check for error messages
                        if 'error' in html.lower() or 'no results' in html.lower():
                            debug_info.append("WARNING: Possible error or no results message")
                        
                        # Parse results
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        tables = soup.find_all('table')
                        debug_info.append(f"Tables found after search: {len(tables)}")
                        
                        # Look for result rows
                        rows = soup.find_all('tr')
                        debug_info.append(f"Total rows found: {len(rows)}")
                        
                        # Check for specific text patterns
                        if 'internal revenue' in html.lower():
                            debug_info.append("✓ Page contains 'internal revenue' text")
                        if 'lien' in html.lower():
                            debug_info.append(f"✓ Page contains 'lien' text ({html.lower().count('lien')} times)")
                        
                        # Try to extract any visible text from result area
                        result_divs = soup.find_all('div', class_=lambda x: x and ('result' in x.lower() if x else False))
                        debug_info.append(f"Result divs found: {len(result_divs)}")
                        
                        # Look for data rows with specific patterns
                        data_rows = []
                        for table in tables:
                            for row in table.find_all('tr'):
                                cells = row.find_all(['td', 'th'])
                                if len(cells) >= 3:  # At least 3 columns
                                    row_text = ' '.join([cell.get_text(strip=True) for cell in cells])
                                    if 'internal revenue' in row_text.lower() or 'lien' in row_text.lower():
                                        data_rows.append(row_text[:100])
                        
                        if data_rows:
                            debug_info.append(f"✓ Found {len(data_rows)} data rows matching criteria")
                            for i, row_text in enumerate(data_rows[:3]):
                                debug_info.append(f"  Row {i}: {row_text}")
                        else:
                            # Try to find any divs with substantial content
                            content_divs = soup.find_all('div', text=lambda t: t and len(t.strip()) > 50)
                            debug_info.append(f"Content divs (>50 chars): {len(content_divs)}")
                            for i, div in enumerate(content_divs[:3]):
                                text = div.get_text(strip=True)[:150]
                                debug_info.append(f"  Content {i}: {text}")
                        
            except Exception as e:
                debug_info.append(f"Form interaction failed: {str(e)}")
            
            return [], debug_info
            
        except Exception as e:
            debug_info.append(f"ERROR: {str(e)}")
            import traceback
            debug_info.append(traceback.format_exc()[:500])
            return [], debug_info
        
    async def scrape(self, from_date: str = None, to_date: str = None, max_results: int = 50) -> List[LienRecord]:
        """Main scraping method"""
        records, _ = await self.scrape_debug(from_date, to_date, max_results)
        return records
