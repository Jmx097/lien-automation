"""
Federal Tax Lien Extraction Pipeline - Main Entry Point
Production-grade Cloud Function for automated lien data extraction
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any

# Import our modules
from browser_automation import NYCACRISAutomation, scrape_nyc_acris
from pdf_extractor import PDFExtractor, FieldExtractor
from field_mapper import FieldMapper, MappedRecord
from accuracy_verifier import AccuracyVerifier, verify_records
from sheets_integration import GoogleSheetsIntegration, SheetWriteResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
SHEET_ID = os.getenv('SHEETS_ID', '1qpstqj-kQje69cFPb-txNV48hpicd-N_4bA1mbD1854')


async def process_site(site_id: str) -> Dict[str, Any]:
    """Process a single site and return results"""
    logger.info(f"Processing site {site_id}")
    
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
            # TODO: Implement Cook County scraper
            logger.warning("Cook County scraper not yet implemented")
            raw_records = []
        elif site_id == '20':  # CA SOS
            # TODO: Implement CA SOS scraper
            logger.warning("CA SOS scraper not yet implemented")
            raw_records = []
        else:
            raise ValueError(f"Unknown site_id: {site_id}")
            
        site_results['records_found'] = len(raw_records)
        logger.info(f"Found {len(raw_records)} records from site {site_id}")
        
        if not raw_records:
            return site_results
            
        # Process each record through extraction pipeline
        mapped_records = []
        
        for raw_record in raw_records:
            try:
                # Step 1: Extract fields from PDF if URL available
                extracted_fields = {}
                if raw_record.pdf_url:
                    pdf_extractor = PDFExtractor()
                    pdf_result = pdf_extractor.extract_from_url(raw_record.pdf_url)
                    
                    field_extractor = FieldExtractor()
                    extracted_fields = field_extractor.extract_all_fields(pdf_result.all_text)
                    
                # Step 2: Map to standardized format
                site_key = {
                    '12': 'nyc_acris',
                    '10': 'cook_county',
                    '20': 'ca_sos'
                }.get(site_id, 'unknown')
                
                mapper = FieldMapper(site_key)
                mapped_record = mapper.map_record(
                    extracted_fields,
                    raw_record.raw_text
                )
                
                mapped_records.append(mapped_record)
                site_results['records_processed'] += 1
                
            except Exception as e:
                logger.error(f"Failed to process record: {e}")
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
                
        logger.info(f"High confidence: {len(high_confidence_records)}, "
                   f"Needs review: {len(low_confidence_records)}")
        
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
            logger.warning(f"{len(low_confidence_records)} records need manual review")
            for record, report in low_confidence_records:
                logger.warning(f"  - {report.record_id}: {report.recommendations}")
                
        return site_results
        
    except Exception as e:
        logger.error(f"Site {site_id} processing failed: {e}")
        site_results['errors'].append(str(e))
        return site_results


def main(request):
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
        "results": [
            {
                "site_id": "12",
                "records_found": 5,
                "records_processed": 5,
                "records_written": 3,
                "duplicates_skipped": 2,
                "errors": []
            }
        ]
    }
    """
    try:
        logger.info("Starting Federal Tax Lien Extraction Pipeline")
        
        # Parse request
        if request and hasattr(request, 'get_json'):
            request_json = request.get_json(silent=True) or {}
        else:
            request_json = {}
            
        # Get sites to process (default to all)
        sites = request_json.get('sites', ['12', '10', '20'])
        logger.info(f"Processing sites: {sites}")
        
        # Process all sites
        all_results = []
        
        for site_id in sites:
            try:
                # Run async processing in sync context
                result = asyncio.run(process_site(site_id))
                all_results.append(result)
            except Exception as e:
                logger.error(f"Failed to process site {site_id}: {e}")
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
        
        logger.info(f"Pipeline complete: {total_written} records written")
        
        return (json.dumps(response, indent=2), 200, {
            'Content-Type': 'application/json'
        })
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
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
            return {'sites': ['12']}  # Test with NYC only
            
    request = MockRequest()
    response = main(request)
    print(response[0])
