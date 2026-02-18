#!/usr/bin/env python3
"""
Debug script for CA UCC Scraper
Runs a single scrape attempt and saves visual artifacts.
"""

import asyncio
import logging
import os
import sys
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.scrapers.ca_ucc_scraper_playwright import CAUCCScraper

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting CA UCC Debug Run")
    
    # Configure debug env vars if not set
    if 'HEADLESS' not in os.environ:
        os.environ['HEADLESS'] = 'false'  # Default to visible for debug
    
    if 'SLOWMO' not in os.environ:
        os.environ['SLOWMO'] = '100'  # 100ms delay for visibility
        
    logger.info(f"HEADLESS: {os.environ.get('HEADLESS')}")
    logger.info(f"SLOWMO: {os.environ.get('SLOWMO')}")
    
    try:
        async with CAUCCScraper() as scraper:
            logger.info(f"Output directory: {scraper.output_dir}")
            
            # Run scrape with 1 day range to avoid >1000 results error
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            records, debug_info = await scraper.scrape_debug(
                from_date=yesterday.strftime("%m/%d/%Y"),
                to_date=yesterday.strftime("%m/%d/%Y"),
                max_results=5
            )
            
            logger.info("-" * 50)
            logger.info(f"Scrape completed. Found {len(records)} records.")
            
            # Print debug info
            print("\nDebug Log:")
            for line in debug_info:
                print(f"  {line}")
                
            # Check for artifacts
            screenshot = os.path.join(scraper.output_dir, "ca_sos_screenshot.png")
            html_dump = os.path.join(scraper.output_dir, "ca_sos_results.html")
            
            if os.path.exists(screenshot):
                logger.info(f"\nScreenshot saved: {screenshot}")
            if os.path.exists(html_dump):
                logger.info(f"HTML dump saved: {html_dump}")
                
    except Exception as e:
        logger.error(f"Debug run failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
