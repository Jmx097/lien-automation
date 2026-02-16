"""
AI Classifier for document classification and field extraction
Uses rule-based classification (can be extended to use ML/AI APIs)
"""
import logging
from typing import Dict, Optional
import re

logger = logging.getLogger(__name__)


class AIClassifier:
    """Classify documents and extract fields using rules + optional AI"""
    
    def __init__(self):
        self.business_indicators = [
            'INC', 'LLC', 'CORP', 'CORPORATION', 'LTD', 'COMPANY',
            'ENTERPRISES', 'SERVICES', 'HOLDINGS', 'PARTNERSHIP',
            'SOLUTIONS', 'GROUP', 'ASSOCIATES'
        ]
    
    def classify_lead_type(self, text: str) -> str:
        """Classify if document is Lien or Release"""
        text_upper = text.upper()
        
        if 'CERTIFICATE OF RELEASE' in text_upper or 'RELEASE OF FEDERAL TAX LIEN' in text_upper:
            return 'Release'
        if 'NOTICE OF FEDERAL TAX LIEN' in text_upper or 'FEDERAL TAX LIEN' in text_upper:
            return 'Lien'
        
        return 'Lien'  # Default
    
    def classify_business_personal(self, name: str, text: str = '') -> str:
        """Classify if taxpayer is Business or Personal"""
        if not name:
            return 'Unknown'
        
        name_upper = ' ' + name.upper() + ' '
        text_upper = text.upper()
        
        # Check for business indicators
        for indicator in self.business_indicators:
            if indicator in name_upper:
                return 'Business'
        
        # Form 941 indicates business
        if ' 941' in text_upper or 'FORM 941' in text_upper:
            return 'Business'
        
        # Check if looks like person name (First Last pattern)
        tokens = [t for t in name.replace(',', ' ').split() if t]
        if len(tokens) >= 2 and len(tokens) <= 4:
            return 'Personal'
        
        return 'Personal'  # Default
    
    def extract_confidence(self, field_name: str, value: Optional[str], 
                          source: str = 'rule_based') -> float:
        """Calculate confidence score for extracted field"""
        if not value:
            return 0.0
        
        base_confidence = 0.7 if source == 'rule_based' else 0.5
        
        # Adjust based on field
        if field_name == 'amount':
            # Higher confidence for well-formatted amounts
            if re.match(r'^\d+$', value):
                base_confidence += 0.1
        
        elif field_name == 'date':
            # Higher confidence for dates in expected format
            if re.match(r'^\d{2}/\d{2}/\d{4}$', value):
                base_confidence += 0.15
        
        return min(base_confidence, 1.0)
