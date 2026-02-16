"""
Utility functions for Lien Automation
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any
import json

# Configure logging
def setup_logging(level=logging.INFO):
    """Setup logging configuration"""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def ensure_directories():
    """Ensure required directories exist"""
    dirs = [
        'downloads',
        'logs',
        'temp',
        'selectors'
    ]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)


def load_field_rules() -> Dict[str, Any]:
    """Load field extraction rules from config"""
    # Default rules - can be expanded
    return {
        'amount_patterns': [
            r'TOTAL\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})',
            r'AMOUNT\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})',
            r'LIEN\s+AMOUNT\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})',
        ],
        'date_patterns': [
            r'DATE\s+OF\s+LIEN\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'LIEN\s+DATE\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'FILED\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ],
        'business_keywords': [
            ' INC', ' LLC', ' COMPANY', ' CO ', ' SERVICE',
            ' SERVICES', ' SOLUTION', ' SOLUTIONS', ' LTD',
            ' LP ', ' LLP ', ' PC ', ' PLLC',
        ]
    }
