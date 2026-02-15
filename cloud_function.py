#!/usr/bin/env python3
"""
Google Cloud Function Entry Point
HTTP-triggered function for Federal Tax Lien extraction.
"""

import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from flask import Request

# Import our modules
from src.config import load_sites_config, get_site_by_id
from src.browser_automation import BrowserAutomation
from src.field_mapper import FieldMapper
from src.sheets_integration import OutputHandler
from src.ai_classifier import AIClassifier
from src.utils import logger, ensure_directories, load_field_rules


class LienExtractionPipeline:
    """Main pipeline orchestrator (Cloud Function compatible)"""
    
    def __init__(self):
        ensure_directories()
        self.sites_config = load_sites_config()
        self.field_rules = load_field_rules()
        self.output_handler = OutputHandler()
        self.ai_classifier = AIClassifier()
        
    async def process_site(
        self,
        site_config: Dict,
        lead_type: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        max_results: int = 10,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Process a single site"""
        start_time = datetime.now().isoformat()
        records = []
        errors = []
        
        logger.info(f"Processing site: {site_config['name']}")
        
        try:
            async with BrowserAutomation(site_config) as browser:
                # Search
                search_results = await browser.perform_search(
                    lead_type=lead_type,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if not search_results:
                    logger.info(f"No results for {site_config['name']}")
                    return {
                        'site_id': site_config['id'],
                        'site_name': site_config['name'],
                        'records_extracted': 0,
                        'records_failed': 0,
                        'errors': [],
                        'start_time': start_time,
                        'end_time': datetime.now().isoformat()
                    }
                
                # Limit results
                if max_results:
                    search_results = search_results[:max_results]
                
                # Process each result
                field_mapper = FieldMapper(site_config, self.field_rules, self.ai_classifier)
                
                for i, result in enumerate(search_results):
                    try:
                        logger.info(f"Processing result {i+1}/{len(search_results)}")
                        
                        # Download
                        pdf_path = await browser.download_document(result)
                        if not pdf_path:
                            errors.append(f"Download failed for result {i}")
                            continue
                        
                        # Map fields
                        record = field_mapper.map_document(
                            pdf_path,
                            result_date=result.get('date')
                        )
                        records.append(record)
                        
                    except Exception as e:
                        error_msg = f"Error processing result {i}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        
                        # Log to Sheets
                        self.output_handler.log_error(
                            site_id=site_config['id'],
                            site_name=site_config['name'],
                            error_msg=str(e),
                            doc_url=result.get('document_url', ''),
                            context={'result_index': i}
                        )
        
        except Exception as e:
            error_msg = f"Site processing failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        # Write results
        if records and not dry_run:
            self.output_handler.write_records(records)
        
        return {
            'site_id': site_config['id'],
            'site_name': site_config['name'],
            'records_extracted': len(records),
            'records_failed': len(errors),
            'errors': errors,
            'start_time': start_time,
            'end_time': datetime.now().isoformat()
        }
    
    async def run(
        self,
        site_ids: List[int] = None,
        all_sites: bool = False,
        lead_type: str = None,
        start_date: str = None,
        end_date: str = None,
        max_results: int = 10,
        dry_run: bool = False
    ) -> List[Dict]:
        """Run extraction for specified sites"""
        
        # Determine sites
        if all_sites:
            sites = [s for s in self.sites_config.get('sites', []) if s.get('enabled')]
        elif site_ids:
            sites = []
            for sid in site_ids:
                site = get_site_by_id(sid)
                if site:
                    sites.append(site)
        else:
            return []
        
        # Parse dates
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            days = int(os.getenv('DEFAULT_DATE_RANGE_DAYS', '7'))
            start_dt = datetime.now() - timedelta(days=days)
        
        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        else:
            end_dt = datetime.now()
        
        # Process each site
        results = []
        for site in sites:
            result = await self.process_site(
                site_config=site,
                lead_type=lead_type,
                start_date=start_dt,
                end_date=end_dt,
                max_results=max_results,
                dry_run=dry_run
            )
            results.append(result)
        
        # Log audit
        total_records = sum(r['records_extracted'] for r in results)
        total_errors = sum(r['records_failed'] for r in results)
        site_results = {r['site_id']: r for r in results}
        
        self.output_handler.log_audit(
            total_records=total_records,
            total_errors=total_errors,
            site_results=site_results
        )
        
        return results


def main(request: Request) -> tuple:
    """
    Google Cloud Function entry point.
    
    Expected JSON body:
    {
        "site_ids": [11, 13, 15],  // or use "all": true
        "lead_type": "Lien",       // optional
        "start_date": "2026-02-01", // optional
        "end_date": "2026-02-13",   // optional
        "max_results": 10,          // optional
        "dry_run": false            // optional
    }
    """
    try:
        # Parse request
        if request.content_type == 'application/json':
            data = request.get_json(silent=True) or {}
        else:
            data = {}
        
        # Extract parameters
        site_ids = data.get('site_ids')
        all_sites = data.get('all', False)
        lead_type = data.get('lead_type')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        max_results = data.get('max_results', 10)
        dry_run = data.get('dry_run', False)
        
        # Validate
        if not site_ids and not all_sites:
            return json.dumps({
                'error': 'Must specify site_ids or set all: true'
            }), 400
        
        # Run pipeline
        pipeline = LienExtractionPipeline()
        results = asyncio.run(pipeline.run(
            site_ids=site_ids,
            all_sites=all_sites,
            lead_type=lead_type,
            start_date=start_date,
            end_date=end_date,
            max_results=max_results,
            dry_run=dry_run
        ))
        
        # Build response
        response = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'sites_processed': len(results),
            'total_records': sum(r['records_extracted'] for r in results),
            'total_errors': sum(r['records_failed'] for r in results),
            'results': results
        }
        
        return json.dumps(response), 200
        
    except Exception as e:
        logger.error(f"Cloud Function error: {e}")
        return json.dumps({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# For local testing
if __name__ == '__main__':
    # Simulate a request
    class MockRequest:
        def __init__(self, json_data):
            self.json_data = json_data
            self.content_type = 'application/json'
        
        def get_json(self, silent=False):
            return self.json_data
    
    # Test with dry run
    test_request = MockRequest({
        'site_ids': [13],
        'max_results': 2,
        'dry_run': True
    })
    
    response_body, status_code = main(test_request)
    print(f"Status: {status_code}")
    print(json.dumps(json.loads(response_body), indent=2))
