#!/usr/bin/env python3
"""
Google Cloud Function Entry Point
HTTP-triggered function for serverless deployment per PRD Section 4.1
"""

import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from flask import Request, Response

# Import local modules
from src.config import load_sites_config, get_site_by_id
from src.browser_automation import BrowserAutomation
from src.field_mapper import FieldMapper
from src.pdf_extractor import PDFExtractor
from src.sheets_integration import OutputHandler
from src.ai_classifier import AIClassifier
from src.utils import logger, ensure_directories


async def process_site(
    site_config: Dict,
    lead_type: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    max_results: int = 10
) -> Dict[str, Any]:
    """Process a single site and return results"""
    site_id = site_config['id']
    site_name = site_config['name']
    
    records_extracted = 0
    records_failed = 0
    errors = []
    
    logger.info(f"Processing site {site_id}: {site_name}")
    
    try:
        async with BrowserAutomation(site_config) as browser:
            # Perform search
            search_results = await browser.perform_search(
                lead_type=lead_type,
                start_date=start_date,
                end_date=end_date
            )
            
            if not search_results:
                logger.info(f"No results found for {site_name}")
                return {
                    'site_id': site_id,
                    'site_name': site_name,
                    'records_extracted': 0,
                    'records_failed': 0,
                    'errors': []
                }
            
            # Limit results
            if max_results:
                search_results = search_results[:max_results]
            
            logger.info(f"Processing {len(search_results)} results from {site_name}")
            
            # Initialize components
            field_mapper = FieldMapper(site_config, {})
            output_handler = OutputHandler()
            
            records = []
            
            for i, result in enumerate(search_results):
                try:
                    # Download document
                    pdf_path = await browser.download_document(result)
                    
                    if not pdf_path:
                        error_msg = f"Failed to download document {result.get('document_id', i)}"
                        errors.append(error_msg)
                        records_failed += 1
                        continue
                    
                    # Map document to record
                    from pathlib import Path
                    record = field_mapper.map_document(
                        Path(pdf_path),
                        result_date=result.get('date')
                    )
                    
                    records.append(record)
                    records_extracted += 1
                    
                except Exception as e:
                    error_msg = f"Error processing result {i}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    records_failed += 1
            
            # Write records
            if records:
                write_result = output_handler.write_records(records)
                logger.info(f"Wrote {write_result.get('written', 0)} records")
    
    except Exception as e:
        error_msg = f"Site processing failed: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
    
    return {
        'site_id': site_id,
        'site_name': site_name,
        'records_extracted': records_extracted,
        'records_failed': records_failed,
        'errors': errors
    }


def main(request: Request) -> Response:
    """
    Cloud Function entry point.
    
    Triggered by HTTP request (from Cloud Scheduler or manual).
    
    Expected JSON body:
    {
        "site_ids": [11, 13, 15],  # Optional: specific sites
        "all_sites": true,         # Optional: process all enabled
        "lead_type": "Lien",       # Optional: Lien or Release
        "start_date": "2026-02-01", # Optional: YYYY-MM-DD
        "end_date": "2026-02-13",   # Optional: YYYY-MM-DD
        "max_results": 10,         # Optional: max per site
        "dry_run": false           # Optional: don't write to Sheets
    }
    """
    ensure_directories()
    
    # Parse request
    try:
        if request.content_type == 'application/json':
            request_json = request.get_json(silent=True) or {}
        else:
            request_json = {}
    except Exception:
        request_json = {}
    
    # Extract parameters
    site_ids = request_json.get('site_ids', [])
    all_sites = request_json.get('all_sites', False)
    lead_type = request_json.get('lead_type')
    start_date_str = request_json.get('start_date')
    end_date_str = request_json.get('end_date')
    max_results = request_json.get('max_results', 10)
    dry_run = request_json.get('dry_run', False)
    
    # Validate auth token if provided
    auth_token = request.headers.get('X-Auth-Token')
    expected_token = os.getenv('AUTH_TOKEN')
    if expected_token and auth_token != expected_token:
        return Response(
            json.dumps({'error': 'Unauthorized'}),
            status=401,
            mimetype='application/json'
        )
    
    # Load sites
    sites_data = load_sites_config()
    sites = sites_data.get('sites', [])
    
    # Filter sites
    if all_sites:
        sites_to_process = [s for s in sites if s.get('enabled', False)]
    elif site_ids:
        sites_to_process = [s for s in sites if s['id'] in site_ids and s.get('enabled', False)]
    else:
        return Response(
            json.dumps({'error': 'No sites specified. Use site_ids or all_sites'}),
            status=400,
            mimetype='application/json'
        )
    
    if not sites_to_process:
        return Response(
            json.dumps({'error': 'No valid sites to process'}),
            status=400,
            mimetype='application/json'
        )
    
    # Parse dates
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        days = int(os.getenv('DEFAULT_DATE_RANGE_DAYS', '7'))
        start_date = datetime.now() - timedelta(days=days)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # Process all sites
    async def run_all():
        results = []
        for site in sites_to_process:
            result = await process_site(
                site,
                lead_type=lead_type,
                start_date=start_date,
                end_date=end_date,
                max_results=max_results
            )
            results.append(result)
        return results
    
    try:
        results = asyncio.run(run_all())
        
        # Calculate totals
        total_extracted = sum(r['records_extracted'] for r in results)
        total_failed = sum(r['records_failed'] for r in results)
        all_errors = [err for r in results for err in r['errors']]
        
        # Log audit
        if not dry_run:
            output_handler = OutputHandler()
            site_results = {r['site_id']: r for r in results}
            output_handler.log_audit(
                total_records=total_extracted,
                total_errors=total_failed,
                site_results=site_results
            )
        
        response_data = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'sites_processed': len(results),
            'total_records_extracted': total_extracted,
            'total_records_failed': total_failed,
            'total_errors': len(all_errors),
            'dry_run': dry_run,
            'results': results
        }
        
        return Response(
            json.dumps(response_data, indent=2),
            status=200,
            mimetype='application/json'
        )
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return Response(
            json.dumps({'error': str(e), 'success': False}),
            status=500,
            mimetype='application/json'
        )


# For local testing
if __name__ == '__main__':
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/', methods=['GET', 'POST'])
    def handler():
        return main(Request.from_values())
    
    print("Starting Cloud Function emulator on http://localhost:8080")
    print("Test with: curl -X POST http://localhost:8080 -H 'Content-Type: application/json' -d '{\"site_ids\": [13], \"max_results\": 2}'")
    app.run(host='0.0.0.0', port=8080)
