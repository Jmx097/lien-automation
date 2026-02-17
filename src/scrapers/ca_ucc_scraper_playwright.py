#!/usr/bin/env python3
"""
California SOS UCC Lien Scraper - Playwright Stealth Version
Uses Playwright with stealth plugins to bypass detection
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json


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
        
        # Launch browser with args to avoid detection
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
        ]
        
        self.browser = await self.playwright.chromium.launch(
            headless=True,
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
        
    async def scrape_debug(self, from_date: str = None, to_date: str = None, max_results: int = 50) -> Tuple[List[LienRecord], List[str]]:
        """Scrape with debug info"""
        if not from_date or not to_date:
            today = datetime.now()
            month_ago = today - timedelta(days=30)
            to_date = today.strftime("%m/%d/%Y")
            from_date = month_ago.strftime("%m/%d/%Y")
        
        debug_info = []
        debug_info.append(f"Date Range: {from_date} to {to_date}")
        
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
            
            # Take screenshot for debugging (save to /tmp)
            try:
                screenshot_path = "/tmp/ca_sos_screenshot.png"
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
                        await search_input.fill('internal revenue service')
                        debug_info.append("✓ Search input filled successfully")
                    except Exception as fill_error:
                        debug_info.append(f"✗ Failed to fill search input: {str(fill_error)}")
                        return [], debug_info
                    
                    # Find and click submit
                    submit_btn = await self.page.query_selector('button[type="submit"], input[type="submit"]')
                    if submit_btn:
                        debug_info.append("Found submit button, clicking...")
                        await submit_btn.click()
                        
                        # Wait for results to load
                        debug_info.append("Waiting 8 seconds for results...")
                        await asyncio.sleep(8)
                        
                        # Check for results
                        html = await self.page.content()
                        debug_info.append(f"After search - HTML length: {len(html)} bytes")
                        
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
