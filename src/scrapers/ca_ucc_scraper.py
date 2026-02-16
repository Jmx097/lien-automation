#!/usr/bin/env python3
"""
California SOS UCC Lien Scraper - ScrapingBee Version
Uses ScrapingBee API with JS scenarios to execute search
"""

import asyncio
import re
import os
import json
import base64
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
    BASE_URL = "https://bizfileonline.sos.ca.gov/search/ucc"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("SCRAPINGBEE_API_KEY")
        if not self.api_key:
            raise ValueError("ScrapingBee API key required. Set SCRAPINGBEE_API_KEY env var.")
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
        
    def build_js_scenario(self, from_date: str, to_date: str) -> List[Dict]:
        """Build JavaScript scenario for ScrapingBee to execute the search"""
        
        # Convert MM/DD/YYYY to YYYY-MM-DD for date inputs
        from_parts = from_date.split("/")
        to_parts = to_date.split("/")
        from_iso = f"{from_parts[2]}-{from_parts[0]}-{from_parts[1]}"
        to_iso = f"{to_parts[2]}-{to_parts[0]}-{to_parts[1]}"
        
        scenario = [
            {"instructions": [{"wait": 3000}]},  # Wait for page load
            {
                "instructions": [
                    {"click": "button.advanced-search-toggle"}  # Click Advanced
                ]
            },
            {"instructions": [{"wait": 2000}]},  # Wait for panel
            {
                "instructions": [
                    {"fill": ["input[type=text]", "internal revenue service"]}  # Fill search
                ]
            },
            {
                "instructions": [
                    {"fill": ["input[type=date]:nth-of-type(1)", from_iso]},  # From date
                    {"fill": ["input[type=date]:nth-of-type(2)", to_iso]}   # To date
                ]
            },
            {
                "instructions": [
                    {"click": "button[type=submit]"}  # Submit search
                ]
            },
            {"instructions": [{"wait": 8000}]}  # Wait for results
        ]
        
        return scenario
        
    async def fetch_with_scenario(self, url: str, scenario: List[Dict]) -> str:
        """Fetch page via ScrapingBee with JS scenario"""
        js_scenario = json.dumps(scenario)
        
        scrapingbee_url = (
            f"https://app.scrapingbee.com/api/v1/?"
            f"api_key={self.api_key}&"
            f"url={url}&"
            f"render_js=true&"
            f"js_scenario={js_scenario}"
        )
        
        print(f"Fetching via ScrapingBee with JS scenario")
        print(f"Scenario steps: {len(scenario)}")
        
        async with self.session.get(scrapingbee_url) as response:
            if response.status != 200:
                text = await response.text()
                print(f"Error {response.status}: {text[:500]}")
                return ""
            html = await response.text()
            print(f"Received {len(html)} bytes")
            return html
            
    def parse_results(self, html: str) -> List[Dict]:
        """Parse UCC results from HTML"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print("BeautifulSoup not installed, using regex fallback")
            return self._parse_with_regex(html)
        
        records = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find result table rows
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables in HTML")
        
        if not tables:
            print("No tables found")
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
                    
                    doc_type = cells[0].get_text(strip=True) if len(cells) > 0 else ""
                    debtor = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                    file_number = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                    secured_party = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                    status = cells[4].get_text(strip=True) if len(cells) > 4 else ""
                    dates = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                    
                    print(f"Row {i}: Type='{doc_type}' | Debtor='{debtor[:30]}' | Secured='{secured_party[:30]}'")
                    
                    # Filter for IRS liens only
                    is_irs = "internal revenue" in secured_party.lower()
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
                        "dates": dates,
                        "lien_or_receive_date": dates.split()[0] if dates else "",
                        "business_personal": self._classify_business_personal(debtor),
                        "company": debtor if self._is_business(debtor) else "",
                        "first_name": "",
                        "last_name": ""
                    }
                    
                    # Parse personal name if applicable
                    if not self._is_business(debtor):
                        name_parts = debtor.split()
                        if len(name_parts) >= 2:
                            record["first_name"] = name_parts[0]
                            record["last_name"] = name_parts[-1]
                    
                    records.append(record)
                    print(f"✓ Found IRS lien: {debtor[:50]}")
                    
                except Exception as e:
                    print(f"Error parsing row {i}: {e}")
                    continue
                    
        return records
        
    def _parse_with_regex(self, html: str) -> List[Dict]:
        """Fallback regex parser if BeautifulSoup not available"""
        records = []
        # Simple regex to find table rows
        row_pattern = r'<tr[^>]*>(.*?)</tr>'
        cell_pattern = r'<td[^>]*>(.*?)</td>'
        
        rows = re.findall(row_pattern, html, re.DOTALL)
        print(f"Regex found {len(rows)} rows")
        
        for i, row_html in enumerate(rows[1:]):
            cells = re.findall(cell_pattern, row_html, re.DOTALL)
            if len(cells) < 4:
                continue
                
            # Strip HTML tags
            clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            
            doc_type = clean_cells[0] if len(clean_cells) > 0 else ""
            debtor = clean_cells[1] if len(clean_cells) > 1 else ""
            secured_party = clean_cells[3] if len(clean_cells) > 3 else ""
            
            if "internal revenue" in secured_party.lower() and "lien" in doc_type.lower():
                records.append({
                    "site_id": "20",
                    "document_type": doc_type,
                    "debtor": debtor,
                    "secured_party": secured_party
                })
                
        return records
        
    def _is_business(self, name: str) -> bool:
        """Check if debtor name is a business"""
        business_keywords = ['INC', 'LLC', 'CORP', 'LTD', 'COMPANY', 'CO.', 'CORPORATION']
        name_upper = name.upper()
        return any(keyword in name_upper for keyword in business_keywords)
        
    def _classify_business_personal(self, name: str) -> str:
        """Classify as Business or Personal"""
        return "Business" if self._is_business(name) else "Personal"
        
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
        print(f"Max Results: {max_results}")
        print(f"{'='*60}\n")
        
        try:
            # Build JS scenario to execute search
            scenario = self.build_js_scenario(from_date, to_date)
            
            # Fetch page with scenario
            html = await self.fetch_with_scenario(self.BASE_URL, scenario)
            
            if not html:
                print("No HTML returned from ScrapingBee")
                return []
            
            # Parse results
            results = self.parse_results(html)
            
            print(f"\nFound {len(results)} IRS lien records")
            return [LienRecord(**r) for r in results[:max_results]]
            
        except Exception as e:
            print(f"Error during scraping: {e}")
            import traceback
            traceback.print_exc()
            return []
