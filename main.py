#!/usr/bin/env python3
"""
Federal Tax Lien Extraction Pipeline - Main Entry Point
Production-grade Cloud Function for automated lien data extraction

Usage:
    # Local testing
    python main.py

    # Cloud Function deployment
    gcloud functions deploy lien_extraction \
        --runtime python311 \
        --trigger-http \
        --entry-point main \
        --memory 1GiB \
        --timeout 300s
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# pylint: disable=wrong-import-position
from src.config import load_sites_config, get_site_by_id  # noqa: E402
from src.browser_automation import scrape_nyc_acris  # noqa: E402
from src.pdf_extractor import PDFExtractor, FieldExtractor  # noqa: E402
from src.field_mapper import FieldMapper  # noqa: E402
from src.accuracy_verifier import verify_records  # noqa: E402
from src.sheets_integration import GoogleSheetsIntegration  # noqa: E402
from src.utils import logger, ensure_directories  # noqa: E402

# Configuration
SHEET_ID = os.getenv('SHEETS_ID', '18C3Qrk3rEXZ9oNocIEUugFLh6q38DRw9JVwznTHoRN0')


async def process_site(site_id: str, max_results: int = 50) -> Dict[str, Any]:
    """Process a single site and return results"""
    logger.info("Processing site %s", site_id)

    site_results = {
        'site_id': site_id,
        'records_found': 0,
        'records_processed': 0,
        'records_written': 0,
        'duplicates_skipped': 0,
        'errors': []
    }

    try:
        # Site-specific processing
        if site_id == '12':  # NYC ACRIS
            raw_records = await scrape_nyc_acris()
        elif site_id == '10':  # Cook County
            logger.warning("Cook County scraper not yet implemented")
            raw_records = []
        elif site_id == '20':  # CA UCC
            from src.scrapers.ca_ucc_scraper_playwright import CAUCCScraper

            # Get ScrapingBee API key
            scrapingbee_key = os.getenv('SCRAPINGBEE_API_KEY')
            if not scrapingbee_key:
                logger.error("SCRAPINGBEE_API_KEY not set")
                site_results['errors'].append("ScrapingBee API key not configured")
                raw_records = []
            else:
                try:
                    async with CAUCCScraper(api_key=scrapingbee_key) as scraper:
                        # Calculate date range (last 30 days for better chances)
                        to_date = datetime.now()
                        from_date = to_date - timedelta(days=30)

                        from_date_str = from_date.strftime("%m/%d/%Y")
                        to_date_str = to_date.strftime("%m/%d/%Y")

                        # Use debug mode to get detailed info
                        lien_records, debug_info = await scraper.scrape_debug(
                            from_date=from_date_str,
                            to_date=to_date_str,
                            max_results=max_results
                        )

                        # Store debug info in results
                        site_results['debug_info'] = debug_info

                        # Convert to raw record format
                        raw_records = []
                        for record in lien_records:
                            # Create a simple object to match expected interface
                            raw_records.append(type('Record', (), {
                                'site_id': '20',
                                'raw_text': json.dumps(record.to_dict()),
                                'pdf_url': None,
                                'filing_date': record.lien_or_receive_date
                            })())

                        logger.info("CA UCC scraper found %d records", len(raw_records))
                except Exception as e:
                    logger.error("CA UCC scraper error: %s", e)
                    site_results['errors'].append(str(e))
                    raw_records = []
        else:
            raise ValueError(f"Unknown site_id: {site_id}")

        site_results['records_found'] = len(raw_records)
        logger.info("Found %d records from site %s", len(raw_records), site_id)

        if not raw_records:
            return site_results

        # Process each record through extraction pipeline
        mapped_records = []

        for raw_record in raw_records:
            try:
                # Step 1: Extract fields from PDF if URL available
                extracted_fields = {}
                if getattr(raw_record, 'pdf_url', None):
                    try:
                        pdf_extractor = PDFExtractor()
                        pdf_result = pdf_extractor.extract_from_url(raw_record.pdf_url)

                        field_extractor = FieldExtractor()
                        extracted_fields = field_extractor.extract_all_fields(pdf_result.all_text)
                    except Exception as e:
                        logger.error("PDF Extraction failed (likely OCR missing): %s", e)
                        # Continue without PDF fields

                # Step 2: Map to standardized format
                site_key = {
                    '12': 'nyc_acris',
                    '10': 'cook_county',
                    '20': 'ca_sos'
                }.get(site_id, 'unknown')

                mapper = FieldMapper(site_key)
                mapped_record = mapper.map_record(
                    extracted_fields,
                    getattr(raw_record, 'raw_text', '') or ''
                )

                mapped_records.append(mapped_record)
                site_results['records_processed'] += 1

            except Exception as e:
                logger.error("Failed to process record: %s", e)
                site_results['errors'].append(str(e))

        # Step 3: Verify accuracy
        verified_results = verify_records(mapped_records)

        # Separate high-confidence from needs-review
        high_confidence_records = []
        low_confidence_records = []

        for record, report in verified_results:
            if report.can_auto_process:
                high_confidence_records.append(record)
            else:
                low_confidence_records.append((record, report))

        logger.info("High confidence: %d, Needs review: %d",
                    len(high_confidence_records), len(low_confidence_records))

        # Step 4: Write to Google Sheets
        if high_confidence_records:
            sheets = GoogleSheetsIntegration(SHEET_ID)

            # Convert to rows
            rows = [record.to_row() for record in high_confidence_records]

            result = sheets.write_liens(rows)

            site_results['records_written'] = result.rows_written
            site_results['duplicates_skipped'] = result.duplicates_skipped

            if result.errors:
                site_results['errors'].extend(result.errors)

        # Log low-confidence records for manual review
        if low_confidence_records:
            logger.warning("%d records need manual review", len(low_confidence_records))
            for record, report in low_confidence_records:
                logger.warning("  - %s: %s", report.record_id, report.recommendations)

        return site_results

    except Exception as e:
        logger.error("Site %s processing failed: %s", site_id, e)
        site_results['errors'].append(str(e))
        return site_results


def main(req):
    """
    Cloud Function entry point

    Expected request body (JSON):
    {
        "sites": ["12", "10", "20"]  // Optional, defaults to all
    }

    Returns:
    {
        "success": true,
        "timestamp": "2024-02-15T12:00:00",
        "results": [...]
    }
    """
    try:
        logger.info("Starting Federal Tax Lien Extraction Pipeline")
        ensure_directories()

        # Parse request
        if req and hasattr(req, 'get_json'):
            request_json = req.get_json(silent=True) or {}
        else:
            request_json = {}

        # Get sites to process (default to all)
        sites = request_json.get('sites', ['12', '10', '20'])
        max_results = request_json.get('max_results', 50)
        logger.info("Processing sites: %s with max_results=%s", sites, max_results)

        # Process all sites
        all_results = []

        for site_id in sites:
            try:
                # Run async processing in sync context
                result = asyncio.run(process_site(site_id, max_results))
                all_results.append(result)
            except Exception as e:
                logger.error("Failed to process site %s: %s", site_id, e)
                all_results.append({
                    'site_id': site_id,
                    'records_found': 0,
                    'records_processed': 0,
                    'records_written': 0,
                    'duplicates_skipped': 0,
                    'errors': [str(e)]
                })

        # Calculate totals
        total_found = sum(r['records_found'] for r in all_results)
        total_written = sum(r['records_written'] for r in all_results)

        response = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'sites_processed': len(sites),
            'total_records_found': total_found,
            'total_records_written': total_written,
            'sheet_url': f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
            'results': all_results
        }

        logger.info("Pipeline complete: %d records written", total_written)

        return (json.dumps(response, indent=2), 200, {
            'Content-Type': 'application/json'
        })

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        error_response = {
            'success': False,
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }
        return (json.dumps(error_response), 500, {
            'Content-Type': 'application/json'
        })


# For local testing
if __name__ == "__main__":
    # Simulate request
    class MockRequest:
        def get_json(self, silent=False):
            # Test with reduced scope and max_results to save credits
            return {'sites': ['12', '20'], 'max_results': 2}

    request = MockRequest()
    res = main(request)
    print(res[0])
