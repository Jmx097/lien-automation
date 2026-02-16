"""
Google Sheets Integration Module
Handles batch writes, deduplication, and error recovery
"""

import os
import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Google Sheets scope
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


@dataclass
class SheetWriteResult:
    """Result of sheet write operation"""
    success: bool
    rows_written: int
    errors: List[str]
    duplicates_skipped: int


class GoogleSheetsIntegration:
    """Integration with Google Sheets for lien data storage"""
    
    def __init__(self, sheet_id: str, service_account_info: Optional[Dict] = None):
        self.sheet_id = sheet_id
        self.service_account_info = service_account_info
        self.client = None
        self.sheet = None
        
        # Tab names
        self.LIENS_TAB = 'Liens'
        self.ERRORS_TAB = 'Errors'
        self.AUDIT_TAB = 'Audit'
        
    def authenticate(self):
        """Authenticate with Google Sheets API"""
        try:
            logger.info("Authenticating with Google Sheets...")
            
            # Try to load service account from Secret Manager (mounted file)
            secret_path = '/secrets/GOOGLE_SERVICE_ACCOUNT_JSON'
            if os.path.exists(secret_path):
                logger.info("Loading credentials from Secret Manager mount...")
                with open(secret_path, 'r') as f:
                    service_account_info = json.load(f)
                creds = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
            # Use provided service account info
            elif self.service_account_info:
                creds = Credentials.from_service_account_info(
                    self.service_account_info,
                    scopes=SCOPES
                )
            else:
                # Try to get from environment variable
                service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
                if service_account_json:
                    creds = Credentials.from_service_account_info(
                        json.loads(service_account_json),
                        scopes=SCOPES
                    )
                else:
                    # Default service account (works in GCP environment)
                    creds = Credentials.get_default(scopes=SCOPES)
            
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.sheet_id)
            
            logger.info("Successfully authenticated with Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise
            
    def get_existing_records(self) -> List[List[str]]:
        """Get all existing records from Liens tab for deduplication"""
        try:
            worksheet = self.sheet.worksheet(self.LIENS_TAB)
            return worksheet.get_all_values()
        except Exception as e:
            logger.warning(f"Could not read existing records: {e}")
            return []
            
    def check_duplicate(self, new_row: List[Any], existing_records: List[List[str]]) -> bool:
        """Check if record already exists (based on key fields)"""
        if not existing_records or len(existing_records) < 2:
            return False
            
        # Skip header row
        data_rows = existing_records[1:]
        
        # Create key from site_id + amount + last_name (or company)
        new_key = self._create_record_key(new_row)
        
        for existing_row in data_rows:
            existing_key = self._create_record_key(existing_row)
            if new_key == existing_key and new_key:  # Non-empty match
                return True
                
        return False
        
    def _create_record_key(self, row: List[Any]) -> str:
        """Create unique key for deduplication"""
        if len(row) < 10:
            return ''
            
        site_id = str(row[0] if row[0] else '')
        amount = str(row[2] if row[2] else '')
        last_name = str(row[9] if row[9] else '')  # Last name or company
        company = str(row[7] if row[7] else '')
        
        # Use company if present, otherwise last_name
        name_key = company if company else last_name
        
        return f"{site_id}_{amount}_{name_key}"
        
    def write_liens(self, records: List[List[Any]], verify_first: bool = True) -> SheetWriteResult:
        """Write lien records to Liens tab with deduplication"""
        try:
            if not self.sheet:
                self.authenticate()
                
            worksheet = self.sheet.worksheet(self.LIENS_TAB)
            
            # Get existing records for deduplication
            existing_records = []
            if verify_first:
                existing_records = self.get_existing_records()
                
            # Filter duplicates
            new_records = []
            duplicates = 0
            
            for record in records:
                if self.check_duplicate(record, existing_records):
                    duplicates += 1
                    logger.info(f"Skipping duplicate record: {record[0:3]}")
                else:
                    new_records.append(record)
                    
            if not new_records:
                logger.info("No new records to write (all duplicates)")
                return SheetWriteResult(
                    success=True,
                    rows_written=0,
                    errors=[],
                    duplicates_skipped=duplicates
                )
                
            # Append new records
            logger.info(f"Writing {len(new_records)} new records to Liens tab")
            worksheet.append_rows(new_records, value_input_option='RAW')
            
            # Log to Audit tab
            self._log_audit(f"Added {len(new_records)} liens", len(new_records))
            
            return SheetWriteResult(
                success=True,
                rows_written=len(new_records),
                errors=[],
                duplicates_skipped=duplicates
            )
            
        except HttpError as e:
            error_msg = f"Google Sheets API error: {e}"
            logger.error(error_msg)
            return SheetWriteResult(
                success=False,
                rows_written=0,
                errors=[error_msg],
                duplicates_skipped=0
            )
        except Exception as e:
            error_msg = f"Failed to write liens: {e}"
            logger.error(error_msg)
            return SheetWriteResult(
                success=False,
                rows_written=0,
                errors=[error_msg],
                duplicates_skipped=0
            )
            
    def write_errors(self, error_records: List[Dict]):
        """Write error records to Errors tab"""
        try:
            if not self.sheet:
                self.authenticate()
                
            worksheet = self.sheet.worksheet(self.ERRORS_TAB)
            
            # Format error records
            rows = []
            for error in error_records:
                row = [
                    error.get('timestamp', ''),
                    error.get('site_id', ''),
                    error.get('error_type', ''),
                    error.get('error_message', ''),
                    error.get('raw_data', ''),
                ]
                rows.append(row)
                
            if rows:
                worksheet.append_rows(rows, value_input_option='RAW')
                logger.info(f"Wrote {len(rows)} errors to Errors tab")
                
        except Exception as e:
            logger.error(f"Failed to write errors: {e}")
            
    def _log_audit(self, action: str, record_count: int):
        """Log action to Audit tab"""
        try:
            worksheet = self.sheet.worksheet(self.AUDIT_TAB)
            
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            
            row = [timestamp, action, str(record_count)]
            worksheet.append_row(row, value_input_option='RAW')
            
        except Exception as e:
            logger.warning(f"Could not write audit log: {e}")
            
    def get_sheet_url(self) -> str:
        """Get URL for the Google Sheet"""
        return f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/edit"


def write_to_sheets(sheet_id: str, records: List[List[Any]], 
                   service_account_info: Optional[Dict] = None) -> SheetWriteResult:
    """Convenience function to write records to Google Sheets"""
    integration = GoogleSheetsIntegration(sheet_id, service_account_info)
    return integration.write_liens(records)
