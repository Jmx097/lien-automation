#!/usr/bin/env python3
"""
CSS Selector Capture Tool for Federal Tax Lien Sites
Guides user through capturing selectors for each county recorder site
"""

import json
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, Page, Browser
except ImportError:
    print("❌ Playwright not installed. Run: pip install playwright && playwright install")
    sys.exit(1)


class SelectorCapture:
    def __init__(self):
        self.captured = {}
        self.current_site = None
        
    def capture_site(self, site_name: str, url: str):
        """Interactive capture for a single site"""
        self.current_site = site_name
        self.captured[site_name] = {
            "url": url,
            "selectors": {}
        }
        
        print(f"\n{'='*60}")
        print(f"🎯 CAPTURING: {site_name}")
        print(f"{'='*60}")
        print(f"URL: {url}")
        print("\nA browser window will open. Follow the prompts.")
        print("Press Enter to start...")
        input()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            
            try:
                page.goto(url, timeout=60000)
                print(f"\n✅ Page loaded: {url}")
                
                # Capture each selector
                self._capture_search_form(page)
                self._capture_results_table(page)
                self._capture_document_page(page)
                
                print(f"\n✅ All selectors captured for {site_name}!")
                
            except Exception as e:
                print(f"\n❌ Error: {e}")
            finally:
                browser.close()
    
    def _capture_search_form(self, page: Page):
        """Capture search form selectors"""
        print("\n" + "-"*60)
        print("STEP 1: Search Form Selectors")
        print("-"*60)
        print("""
Instructions:
1. Use Chrome DevTools (F12) → Elements tab
2. Right-click the element → Copy → Copy selector
3. Paste the selector below

Need to capture:
• Document type dropdown (select "Federal Tax Lien")
• Date 'from' input field
• Date 'to' input field  
• Search button
""")
        
        self.captured[self.current_site]["selectors"]["search_form"] = {
            "document_type_dropdown": input("Document type dropdown selector: ").strip(),
            "date_from_input": input("Date 'from' input selector: ").strip(),
            "date_to_input": input("Date 'to' input selector: ").strip(),
            "search_button": input("Search button selector: ").strip(),
        }
    
    def _capture_results_table(self, page: Page):
        """Capture results table selectors"""
        print("\n" + "-"*60)
        print("STEP 2: Results Table Selectors")
        print("-"*60)
        print("""
Instructions:
First, perform a search with these dates:
  From: 02/01/2026
  To: 02/13/2026
  Document Type: Federal Tax Lien

Then capture:
• Table container (wrapper around all results)
• Row selector (each result row)
• Date column (filing date cell)
• Document link (link to view document)
""")
        
        input("\nPress Enter after you've performed the search...")
        
        self.captured[self.current_site]["selectors"]["results_table"] = {
            "table_container": input("Table container selector: ").strip(),
            "rows": input("Row selector (e.g., 'tbody tr'): ").strip(),
            "date_column": input("Date column selector (e.g., 'td:nth-child(1)'): ").strip(),
            "document_link": input("Document link selector: ").strip(),
            "next_page_button": input("Next page button selector (or leave blank): ").strip() or None,
        }
    
    def _capture_document_page(self, page: Page):
        """Capture document page selectors"""
        print("\n" + "-"*60)
        print("STEP 3: Document Page Selectors")
        print("-"*60)
        print("""
Instructions:
Click on a document from the search results.
Then capture:
• PDF/Image download link
• Recorder stamp date (if shown on page)
• Document details container
""")
        
        input("\nPress Enter after you've opened a document...")
        
        self.captured[self.current_site]["selectors"]["document_page"] = {
            "pdf_download_link": input("PDF download link selector: ").strip(),
            "document_details": input("Document details container selector: ").strip(),
            "recorder_stamp": input("Recorder stamp date selector (or leave blank): ").strip() or None,
        }
    
    def save_results(self, output_file: str = "captured_selectors.json"):
        """Save captured selectors to JSON"""
        output_path = Path(output_file)
        
        # Merge with existing if file exists
        if output_path.exists():
            with open(output_path) as f:
                existing = json.load(f)
            existing.update(self.captured)
            self.captured = existing
        
        with open(output_path, 'w') as f:
            json.dump(self.captured, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        print("\n📤 Next steps:")
        print("1. Upload this file to your OpenClaw workspace")
        print("2. I'll integrate these selectors into sites.json")


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     CSS SELECTOR CAPTURE TOOL                               ║
║     Federal Tax Lien Automation System                      ║
╚══════════════════════════════════════════════════════════════╝

This tool will help you capture CSS selectors from county recorder sites.
You'll need Chrome DevTools (F12) to copy selectors.

Sites to capture:
  1. AZ Maricopa County
  2. TX Dallas County  
  3. FL Miami-Dade County
""")
    
    sites = [
        ("AZ Maricopa", "https://recorder.maricopa.gov/recording/document-search.html"),
        ("TX Dallas", "https://dallas.tx.publicsearch.us/"),
        ("FL Miami-Dade", "https://onlineservices.miamidadeclerk.gov/officialrecords"),
    ]
    
    capture = SelectorCapture()
    
    for site_name, url in sites:
        capture.capture_site(site_name, url)
    
    capture.save_results()
    
    print("\n" + "="*60)
    print("🎉 ALL DONE!")
    print("="*60)
    print("\nUpload 'captured_selectors.json' to OpenClaw and I'll")
    print("update your sites.json configuration automatically.")


if __name__ == "__main__":
    main()
