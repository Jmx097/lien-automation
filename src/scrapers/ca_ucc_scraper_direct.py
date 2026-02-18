#!/usr/bin/env python3
"""
California SOS UCC Lien Scraper - Direct HTTP Version
Tries simple HTTP requests without headless browser
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import aiohttp


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
    """
    Direct HTTP scraper for CA UCC (fallback method)
    Note: Most sites require JavaScript, so this is limited
    """
    
    BASE_URL = "https://bizfileonline.sos.ca.gov/search/ucc"
    
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        # Use a session with realistic browser headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.session = aiohttp.ClientSession(headers=headers)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        
    async def scrape_debug(self, from_date: str = None, to_date: str = None, max_results: int = 50) -> tuple:
        """
        Scrape with debug info - direct HTTP attempt
        Note: CA SOS requires JavaScript, so this will likely return limited results
        """
        if not from_date or not to_date:
            today = datetime.now()
            month_ago = today - timedelta(days=30)
            to_date = today.strftime("%m/%d/%Y")
            from_date = month_ago.strftime("%m/%d/%Y")
        
        debug_info = []
        debug_info.append(f"Date Range: {from_date} to {to_date}")
        debug_info.append("WARNING: Direct HTTP mode - site requires JavaScript")
        debug_info.append("Use ca_ucc_scraper_playwright.py for full functionality")
        
        # Try direct HTTP request with browser headers
        try:
            debug_info.append("Attempting direct HTTP request...")
            async with self.session.get(self.BASE_URL, timeout=30) as response:
                html = await response.text()
                debug_info.append(f"HTTP status: {response.status}")
                debug_info.append(f"Response length: {len(html)} bytes")
                
                # Parse to see what we got
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                title = soup.find('title')
                if title:
                    debug_info.append(f"Page title: {title.get_text()}")
                
                # Check for JavaScript requirements
                if 'enable javascript' in html.lower() or 'javascript required' in html.lower():
                    debug_info.append("CONFIRMED: Site requires JavaScript execution")
                
                # Look for forms
                forms = soup.find_all('form')
                debug_info.append(f"Forms found: {len(forms)}")
                
                # Look for iframes (common in JS-heavy sites)
                iframes = soup.find_all('iframe')
                debug_info.append(f"Iframes found: {len(iframes)}")
                
        except Exception as e:
            debug_info.append(f"Direct HTTP failed: {str(e)}")
        
        debug_info.append("Direct HTTP mode complete - use Playwright for full extraction")
        return [], debug_info
    
    async def scrape(self, from_date: str = None, to_date: str = None, max_results: int = 50) -> List[LienRecord]:
        """Main scraping method"""
        records, _ = await self.scrape_debug(from_date, to_date, max_results)
        return records
