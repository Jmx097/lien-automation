#!/usr/bin/env python3
"""
SIMPLE Selector Helper - Single Site Mode
Run this for just one site at a time if you prefer
"""

import json
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("pip install playwright && playwright install")
    sys.exit(1)

SITES = {
    "11": ("AZ Maricopa", "https://recorder.maricopa.gov/recording/document-search.html"),
    "13": ("TX Dallas", "https://dallas.tx.publicsearch.us/"),
    "15": ("FL Miami-Dade", "https://onlineservices.miamidadeclerk.gov/officialrecords"),
}

def capture_one_site(site_id: str):
    name, url = SITES[site_id]
    print(f"\n🎯 Opening {name}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(url)
        
        print(f"\n✅ Browser opened: {url}")
        print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAPTURE TEMPLATE (copy this and fill it in):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Search Form:
  Document type dropdown: ___________________
  Date 'from' input:      ___________________
  Date 'to' input:        ___________________
  Search button:          ___________________

Results Table:
  Table container:        ___________________
  Row selector:           ___________________
  Date column:            ___________________
  Document link:          ___________________
  Next page button:       ___________________ (or "none")

Document Page:
  PDF download link:      ___________________
  Document details:       ___________________
  Recorder stamp date:    ___________________ (or "none")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
        
        input("Press Enter when you're ready to close the browser...")
        browser.close()
    
    print(f"\nNow create a file called '{site_id}_selectors.txt' with your captured selectors.")

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SITES:
        print("Usage: python capture_one_site.py <site_id>")
        print(f"  Sites: {', '.join(SITES.keys())}")
        sys.exit(1)
    
    capture_one_site(sys.argv[1])
