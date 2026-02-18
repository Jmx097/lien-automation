#!/usr/bin/env python3
"""
Debug runner for CA UCC Scraper.
Runs non-headless by default (Incapsula blocks headless).
Saves all artifacts to TEMP dir.
"""
import asyncio
import logging
import os
import sys
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Force non-headless (Incapsula blocks headless Chromium)
os.environ.setdefault('HEADLESS', 'false')
os.environ.setdefault('SLOWMO', '100')

logging.basicConfig(level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    from scrapers.ca_ucc_scraper_playwright import CAUCCScraper

    # Parse CLI args
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=7, help='Date range in days')
    parser.add_argument('--page', type=int, default=1, help='Page number to fetch')
    parser.add_argument('--max', type=int, default=10, help='Max results')
    args = parser.parse_args()

    today = datetime.now()
    start_date = today - timedelta(days=args.days)
    from_date = start_date.strftime("%m/%d/%Y")
    to_date = today.strftime("%m/%d/%Y")

    logger.info(f"=== CA UCC Debug Run ===")
    logger.info(f"Date range: {from_date} → {to_date} ({args.days} days)")
    logger.info(f"Page: {args.page}  |  Max results: {args.max}")
    logger.info(f"HEADLESS: {os.environ.get('HEADLESS')}")
    logger.info(f"SLOWMO: {os.environ.get('SLOWMO')}")

    try:
        async with CAUCCScraper() as scraper:
            logger.info(f"Output dir: {scraper.output_dir}")

            records, log = await scraper.scrape_debug(
                from_date=from_date,
                to_date=to_date,
                max_results=args.max,
                page_number=args.page,
            )

            logger.info("=" * 60)
            logger.info("EXECUTION LOG:")
            for line in log:
                logger.info(f"  {line}")
            logger.info("=" * 60)
            logger.info(f"Records found: {len(records)}")
            for i, r in enumerate(records[:5]):
                logger.info(f"  [{i}] {r.to_dict()}")

            # Check verification targets
            detail_html = os.path.join(scraper.output_dir, "04_detail.html")
            final_url = os.path.join(scraper.output_dir, "final_url.txt")
            if os.path.exists(detail_html) and os.path.getsize(detail_html) > 0:
                logger.info(f"✓ detail.html exists ({os.path.getsize(detail_html)} bytes)")
            else:
                logger.info(f"✗ detail.html not found or empty")
            if os.path.exists(final_url):
                with open(final_url) as f:
                    logger.info(f"✓ final_url.txt: {f.read().strip()}")
            else:
                logger.info(f"✗ final_url.txt not found")

    except Exception as e:
        logger.error(f"Debug run failed: {e}", exc_info=True)

if __name__ == '__main__':
    asyncio.run(main())
