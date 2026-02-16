#!/usr/bin/env python3
"""
California SOS UCC Lien Scraper - ScrapingBee Version
Uses ScrapingBee API to bypass headless browser detection
"""

import asyncio
import re
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
import aiohttp


@dataclass
class LienRecord:
    site_id: str = "20"  # CA UCC Site
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
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SCRAPINGBEE_API_KEY")
        if not self.api_key:
            raise ValueError("ScrapingBee API key required")
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
        
    async def fetch_page(self, url: str, wait_ms: int = 5000) -> str:
        """Fetch page via ScrapingBee API"""
        scrapingbee_url = (
            f"https://app.scrapingbee.com/api/v1/?"
            f"api_key={self.api_key}&"
            f"url={url}&"
            f"render_js=true&"
            f"wait={wait_ms}"
        )
        
        print(f"Fetching via ScrapingBee: {url}")
        async with self.session.get(scrapingbee_url) as response:
            html = await response.text()
            print(f"Received {len(html)} bytes")
            return html
            
    def parse_results(self, html: str) -> List[Dict]:
        """Parse UCC results from HTML"""
        from bs4 import BeautifulSoup
        
        records = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find result table rows
        # Based on the selector user provided: #root > div > div.content > div > main > div.table-wrapper > table > tbody > tr
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables in HTML")
        
        if not tables:
            print("No tables found - site may have different structure")
            return records
            
        # Try to find the results table
        for table in tables:
            rows = table.find_all('tr')
            print(f"Table has {len(rows)} rows")
            
            for i, row in enumerate(rows[1:]):  # Skip header
                try:
                    cells = row.find_all('td')
                    if len(cells) < 4:
                        continue
                    
                    # Extract cell text
                    doc_type = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    debtor = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    file_number = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    secured_party = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    status = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    dates = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                    
                    print(f"Row {i}: Type='{doc_type}' | Debtor='{debtor[:30]}' | Secured='{secured_party[:30]}'")
                    
                    # Filter for IRS liens only
                    is_irs = "internal revenue" in secured_party.lower() or "internal revenue" in debtor.lower()
                    is_lien = "federal tax lien" in doc_type.lower() or "tax lien" in doc_type.lower()
                    
                    if not is_irs or not is_lien:
                        continue
                    
                    record = {
                        "site_id": "20",
                        "document_type": doc_type,
                        "debtor": debtor,
                        "file_number": file_number,
                        "secured_party": secured_party,
                        "status": status,
                        "dates": dates
                    }
                    
                    records.append(record)
                    print(f"✓ Found IRS lien: {debtor[:50]}")
                    
                except Exception as e:
                    print(f"Error parsing row {i}: {e}")
                    continue
                    
        return records
        
    async def scrape(self, from_date: str = None, to_date: str = None, max_results: int = 50) -> List[LienRecord]:
        """Main scraping method"""
        # Calculate default date range (last 7 days)
        if not from_date or not to_date:
            today = datetime.now()
            week_ago = today - timedelta(days=7)
            to_date = today.strftime("%m/%d/%Y")
            from_date = week_ago.strftime("%m/%d/%Y")
        
        print(f"\n{'='*60}")
        print(f"CA UCC Lien Scraper (ScrapingBee)")
        print(f"Date Range: {from_date} to {to_date}")
        print(f"{'='*60}\n")
        
        try:
            # Note: ScrapingBee will execute the search via JavaScript
            # We'll need to construct the search URL with parameters
            # For now, fetch the base page to test
            
            html = await self.fetch_page(self.BASE_URL, wait_ms=8000)
            results = self.parse_results(html)
            
            print(f"\nFound {len(results)} IRS lien records")
            return [LienRecord(**r) for r in results[:max_results]]
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            import traceback
            traceback.print_exc()
            return []
