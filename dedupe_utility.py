"""
Dedupe Utility for Google Sheets Lien Data
Removes duplicate records and cleans up the Liens tab
"""

import logging
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass

from sheets_integration import GoogleSheetsIntegration

logger = logging.getLogger(__name__)


@dataclass
class DedupeResult:
    """Result of deduplication process"""
    total_rows: int
    unique_rows: int
    duplicates_found: int
    duplicates_removed: int
    rows_written: int


class SheetsDeduper:
    """Deduplication utility for lien data in Google Sheets"""
    
    def __init__(self, sheet_id: str):
        self.sheet_id = sheet_id
        self.sheets = GoogleSheetsIntegration(sheet_id)
        
    def find_duplicates(self, rows: List[List[str]], 
                       key_columns: List[int] = None) -> Dict[str, List[int]]:
        """
        Find duplicate rows based on key columns
        
        Args:
            rows: All rows from sheet (including header)
            key_columns: Column indices to use for dedupe (default: 0, 2, 9 = site_id, amount, last_name)
            
        Returns:
            Dict mapping key to list of row indices that are duplicates
        """
        if not rows or len(rows) < 2:
            return {}
            
        if key_columns is None:
            # Default: site_id (0) + amount (2) + last_name (9)
            key_columns = [0, 2, 9]
            
        header = rows[0]
        data_rows = rows[1:]
        
        seen: Dict[str, int] = {}  # key -> first row index
        duplicates: Dict[str, List[int]] = {}
        
        for idx, row in enumerate(data_rows):
            # Build key from specified columns
            key_parts = []
            for col_idx in key_columns:
                if col_idx < len(row):
                    key_parts.append(str(row[col_idx]).strip().upper())
                else:
                    key_parts.append('')
                    
            key = '_'.join(key_parts)
            
            if key in seen:
                if key not in duplicates:
                    duplicates[key] = [seen[key]]  # First occurrence
                duplicates[key].append(idx)
            else:
                seen[key] = idx
                
        return duplicates
        
    def dedupe_sheet(self, dry_run: bool = True) -> DedupeResult:
        """
        Remove duplicates from the Liens tab
        
        Args:
            dry_run: If True, only report what would be removed
            
        Returns:
            DedupeResult with statistics
        """
        logger.info(f"Starting deduplication (dry_run={dry_run})")
        
        # Get all existing records
        all_rows = self.sheets.get_existing_records()
        
        if not all_rows or len(all_rows) < 2:
            logger.info("No data to dedupe")
            return DedupeResult(0, 0, 0, 0, 0)
            
        header = all_rows[0]
        data_rows = all_rows[1:]
        
        total_rows = len(data_rows)
        logger.info(f"Found {total_rows} data rows (plus header)")
        
        # Find duplicates
        duplicates = self.find_duplicates(all_rows)
        
        if not duplicates:
            logger.info("No duplicates found")
            return DedupeResult(total_rows, total_rows, 0, 0, total_rows)
            
        # Calculate which rows to keep
        rows_to_remove: Set[int] = set()
        for key, indices in duplicates.items():
            # Keep first occurrence, mark rest for removal
            logger.info(f"Duplicate key '{key}' found at rows: {[i+2 for i in indices]}")  # +2 for 1-indexed and header
            rows_to_remove.update(indices[1:])  # Skip first occurrence
            
        duplicates_found = sum(len(indices) - 1 for indices in duplicates.values())
        
        # Build deduped list
        deduped_rows = []
        for idx, row in enumerate(data_rows):
            if idx not in rows_to_remove:
                deduped_rows.append(row)
                
        unique_rows = len(deduped_rows)
        
        logger.info(f"Deduplication report:")
        logger.info(f"  Total rows: {total_rows}")
        logger.info(f"  Unique rows: {unique_rows}")
        logger.info(f"  Duplicates found: {duplicates_found}")
        logger.info(f"  Rows to remove: {len(rows_to_remove)}")
        
        if not dry_run and rows_to_remove:
            # Clear sheet and rewrite
            logger.info("Applying deduplication...")
            
            worksheet = self.sheets.sheet.worksheet(self.sheets.LIENS_TAB)
            
            # Clear all data except header
            if len(all_rows) > 1:
                worksheet.delete_rows(2, len(all_rows))
                
            # Write deduped data
            if deduped_rows:
                worksheet.append_rows(deduped_rows, value_input_option='RAW')
                
            # Log to audit
            self.sheets._log_audit(
                f"Deduped {duplicates_found} duplicates, {unique_rows} unique remaining",
                unique_rows
            )
            
            logger.info(f"Deduplication complete. {unique_rows} rows in sheet.")
            
        return DedupeResult(
            total_rows=total_rows,
            unique_rows=unique_rows,
            duplicates_found=duplicates_found,
            duplicates_removed=len(rows_to_remove) if not dry_run else 0,
            rows_written=unique_rows if not dry_run else total_rows
        )
        
    def preview_duplicates(self) -> List[Dict]:
        """Preview duplicates without removing them"""
        all_rows = self.sheets.get_existing_records()
        
        if not all_rows or len(all_rows) < 2:
            return []
            
        duplicates = self.find_duplicates(all_rows)
        
        preview = []
        for key, indices in duplicates.items():
            preview.append({
                'key': key,
                'row_numbers': [i + 2 for i in indices],  # 1-indexed with header
                'count': len(indices),
                'sample_data': all_rows[indices[0] + 1][:5]  # First 5 columns
            })
            
        return preview


def run_dedupe(sheet_id: str, dry_run: bool = True) -> DedupeResult:
    """Convenience function to run deduplication"""
    deduper = SheetsDeduper(sheet_id)
    return deduper.dedupe_sheet(dry_run=dry_run)


if __name__ == "__main__":
    import os
    
    # Use environment variable or default
    sheet_id = os.getenv('SHEETS_ID', '1qpstqj-kQje69cFPb-txNV48hpicd-N_4bA1mbD1854')
    
    # Run preview first
    print("Previewing duplicates...")
    deduper = SheetsDeduper(sheet_id)
    preview = deduper.preview_duplicates()
    
    if preview:
        print(f"\nFound {len(preview)} duplicate groups:")
        for dup in preview:
            print(f"  Key: {dup['key']}")
            print(f"  Rows: {dup['row_numbers']}")
            print(f"  Sample: {dup['sample_data']}")
            print()
    else:
        print("No duplicates found!")
        
    # Ask to proceed
    response = input("\nRemove duplicates? (yes/no): ")
    if response.lower() == 'yes':
        result = run_dedupe(sheet_id, dry_run=False)
        print(f"\nResult:")
        print(f"  Total: {result.total_rows}")
        print(f"  Unique: {result.unique_rows}")
        print(f"  Removed: {result.duplicates_removed}")
    else:
        print("Cancelled.")
