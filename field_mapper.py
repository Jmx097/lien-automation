"""
Field Mapper Module
Maps extracted PDF data to standardized Google Sheet format per Mapping Guide
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MappedField:
    """Single mapped field with confidence and source"""
    value: Optional[str]
    confidence: float  # 0.0 to 1.0
    source: str  # 'pdf_text', 'ocr', 'inferred', 'manual'
    verification_note: Optional[str] = None


@dataclass
class MappedRecord:
    """Complete mapped record ready for Google Sheets"""
    site_id: str
    lien_or_receive_date: MappedField
    amount: MappedField
    lead_type: MappedField
    lead_source: MappedField
    liability_type: MappedField
    business_personal: MappedField
    company: MappedField
    first_name: MappedField
    last_name: MappedField
    street: MappedField
    city: MappedField
    state: MappedField
    zip_code: MappedField
    
    def to_row(self) -> List[Any]:
        """Convert to Google Sheets row format"""
        return [
            self.site_id,
            self.lien_or_receive_date.value,
            self.amount.value,
            self.lead_type.value,
            self.lead_source.value,
            self.liability_type.value,
            self.business_personal.value,
            self.company.value,
            self.first_name.value,
            self.last_name.value,
            self.street.value,
            self.city.value,
            self.state.value,
            self.zip_code.value,
        ]
        
    def get_confidence_scores(self) -> Dict[str, float]:
        """Get all confidence scores for verification"""
        return {
            'lien_or_receive_date': self.lien_or_receive_date.confidence,
            'amount': self.amount.confidence,
            'lead_type': self.lead_type.confidence,
            'lead_source': self.lead_source.confidence,
            'liability_type': self.liability_type.confidence,
            'business_personal': self.business_personal.confidence,
            'company': self.company.confidence,
            'first_name': self.first_name.confidence,
            'last_name': self.last_name.confidence,
            'street': self.street.confidence,
            'city': self.city.confidence,
            'state': self.state.confidence,
            'zip_code': self.zip_code.confidence,
        }


class FieldMapper:
    """Map extracted PDF fields to standardized format per Mapping Guide"""
    
    # Site ID mapping
    SITE_IDS = {
        'nyc_acris': '12',
        'cook_county': '10',
        'ca_sos': '20',
    }
    
    # Liability types per site
    LIABILITY_TYPES = {
        'nyc_acris': 'IRS',
        'cook_county': 'IRS',
        'ca_sos': 'IRS',
    }
    
    def __init__(self, site_key: str):
        self.site_key = site_key
        self.site_id = self.SITE_IDS.get(site_key, '00')
        self.liability_type = self.LIABILITY_TYPES.get(site_key, 'IRS')
        
    def map_record(self, extracted_fields: Dict[str, str], raw_text: str) -> MappedRecord:
        """Map extracted fields to standardized record"""
        logger.info(f"Mapping record for site {self.site_key}")
        
        # Map each field with confidence scoring
        record = MappedRecord(
            site_id=self.site_id,
            lien_or_receive_date=self._map_date(extracted_fields, raw_text),
            amount=self._map_amount(extracted_fields, raw_text),
            lead_type=self._map_lead_type(),
            lead_source=self._map_lead_source(),
            liability_type=self._map_liability_type(),
            business_personal=self._map_business_personal(extracted_fields, raw_text),
            company=self._map_company(extracted_fields, raw_text),
            first_name=self._map_first_name(extracted_fields, raw_text),
            last_name=self._map_last_name(extracted_fields, raw_text),
            street=self._map_street(extracted_fields, raw_text),
            city=self._map_city(extracted_fields, raw_text),
            state=self._map_state(extracted_fields, raw_text),
            zip_code=self._map_zip_code(extracted_fields, raw_text),
        )
        
        return record
        
    def _map_date(self, fields: Dict, raw_text: str) -> MappedField:
        """Map lien date field"""
        date_value = fields.get('lien_date') or fields.get('date')
        
        if date_value:
            # Normalize date format
            normalized = self._normalize_date(date_value)
            return MappedField(
                value=normalized,
                confidence=0.85,
                source='pdf_text',
                verification_note='Extracted from lien document'
            )
        else:
            # Try to extract from raw text
            date_patterns = [
                r'(\d{1,2}/\d{1,2}/\d{4})',
                r'(\d{1,2}-\d{1,2}-\d{4})',
            ]
            for pattern in date_patterns:
                match = re.search(pattern, raw_text)
                if match:
                    return MappedField(
                        value=self._normalize_date(match.group(1)),
                        confidence=0.70,
                        source='inferred',
                        verification_note='Date inferred from document text'
                    )
                    
        return MappedField(
            value=None,
            confidence=0.0,
            source='manual',
            verification_note='Date not found - manual review required'
        )
        
    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to MM/DD/YYYY format"""
        try:
            # Remove extra spaces
            date_str = date_str.strip()
            
            # Handle various formats
            if '/' in date_str:
                parts = date_str.split('/')
            elif '-' in date_str:
                parts = date_str.split('-')
            else:
                return date_str
                
            if len(parts) == 3:
                month, day, year = parts
                # Ensure 4-digit year
                if len(year) == 2:
                    year_int = int(year)
                    if year_int >= 50:
                        year = '19' + year
                    else:
                        year = '20' + year
                return f"{month.zfill(2)}/{day.zfill(2)}/{year}"
                
        except Exception as e:
            logger.warning(f"Date normalization failed: {e}")
            
        return date_str
        
    def _map_amount(self, fields: Dict, raw_text: str) -> MappedField:
        """Map amount field - remove $ and commas"""
        amount_value = fields.get('amount')
        
        if amount_value:
            # Clean amount
            cleaned = re.sub(r'[$,]', '', amount_value)
            # Validate it's a number
            try:
                float(cleaned)
                return MappedField(
                    value=cleaned,
                    confidence=0.90,
                    source='pdf_text',
                    verification_note='Amount extracted from lien document'
                )
            except ValueError:
                pass
                
        # Try to find any dollar amount
        amount_pattern = r'\$?([\d,]+\.\d{2})'
        matches = re.findall(amount_pattern, raw_text)
        if matches:
            # Take largest amount (usually the lien amount)
            amounts = [float(re.sub(r',', '', m)) for m in matches]
            largest = max(amounts)
            return MappedField(
                value=str(int(largest)),
                confidence=0.75,
                source='inferred',
                verification_note='Largest amount in document used'
            )
            
        return MappedField(
            value=None,
            confidence=0.0,
            source='manual',
            verification_note='Amount not found - manual review required'
        )
        
    def _map_lead_type(self) -> MappedField:
        """Lead type is always 'Lien' for Federal Tax Liens"""
        return MappedField(
            value='Lien',
            confidence=1.0,
            source='inferred',
            verification_note='Always Lien for Federal Tax Lien documents'
        )
        
    def _map_lead_source(self) -> MappedField:
        """Lead source is always '777' per Mapping Guide"""
        return MappedField(
            value='777',
            confidence=1.0,
            source='inferred',
            verification_note='Always 777 per Mapping Guide'
        )
        
    def _map_liability_type(self) -> MappedField:
        """Liability type per site configuration"""
        return MappedField(
            value=self.liability_type,
            confidence=1.0,
            source='inferred',
            verification_note=f'Site {self.site_key} uses {self.liability_type}'
        )
        
    def _map_business_personal(self, fields: Dict, raw_text: str) -> MappedField:
        """Determine if Business or Personal based on taxpayer name"""
        taxpayer = fields.get('taxpayer_name', '')
        
        # Business indicators
        business_indicators = [
            'INC', 'LLC', 'CORP', 'CORPORATION', 'LTD', 'COMPANY',
            'ENTERPRISES', 'SERVICES', 'HOLDINGS', 'PARTNERSHIP'
        ]
        
        taxpayer_upper = taxpayer.upper()
        
        for indicator in business_indicators:
            if indicator in taxpayer_upper:
                return MappedField(
                    value='Business',
                    confidence=0.85,
                    source='inferred',
                    verification_note=f'Business indicator "{indicator}" found in name'
                )
                
        # Check for individual indicators
        # If name looks like "First Last" (no business suffix), assume Personal
        if taxpayer and not any(ind in taxpayer_upper for ind in business_indicators):
            return MappedField(
                value='Personal',
                confidence=0.75,
                source='inferred',
                verification_note='No business indicators found - assumed personal'
            )
            
        return MappedField(
            value='Unknown',
            confidence=0.30,
            source='manual',
            verification_note='Could not determine business/personal - manual review'
        )
        
    def _map_company(self, fields: Dict, raw_text: str) -> MappedField:
        """Map company name - only for Business leads"""
        business_personal = self._map_business_personal(fields, raw_text)
        
        if business_personal.value == 'Business':
            company_name = fields.get('taxpayer_name', '')
            return MappedField(
                value=company_name,
                confidence=0.80,
                source='pdf_text',
                verification_note='Company name from taxpayer field'
            )
        else:
            return MappedField(
                value='',
                confidence=1.0,
                source='inferred',
                verification_note='Personal lead - no company name'
            )
            
    def _map_first_name(self, fields: Dict, raw_text: str) -> MappedField:
        """Extract first name from personal taxpayer"""
        business_personal = self._map_business_personal(fields, raw_text)
        
        if business_personal.value == 'Personal':
            full_name = fields.get('taxpayer_name', '')
            parts = full_name.split()
            if len(parts) >= 2:
                return MappedField(
                    value=parts[0],
                    confidence=0.70,
                    source='inferred',
                    verification_note='First word of taxpayer name'
                )
                
        return MappedField(
            value='',
            confidence=1.0,
            source='inferred',
            verification_note='Business lead - no first name'
        )
        
    def _map_last_name(self, fields: Dict, raw_text: str) -> MappedField:
        """Extract last name from personal taxpayer"""
        business_personal = self._map_business_personal(fields, raw_text)
        
        if business_personal.value == 'Personal':
            full_name = fields.get('taxpayer_name', '')
            parts = full_name.split()
            if len(parts) >= 2:
                return MappedField(
                    value=parts[-1],
                    confidence=0.70,
                    source='inferred',
                    verification_note='Last word of taxpayer name'
                )
                
        return MappedField(
            value='',
            confidence=1.0,
            source='inferred',
            verification_note='Business lead - no last name'
        )
        
    def _map_street(self, fields: Dict, raw_text: str) -> MappedField:
        """Extract street address"""
        address = fields.get('address', '')
        
        if address:
            return MappedField(
                value=address,
                confidence=0.80,
                source='pdf_text',
                verification_note='Address extracted from document'
            )
            
        # Try to extract from raw text
        street_pattern = r'(\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Plaza|Plz|Suite|Ste|Floor|Fl))'
        match = re.search(street_pattern, raw_text, re.IGNORECASE)
        if match:
            return MappedField(
                value=match.group(1),
                confidence=0.65,
                source='inferred',
                verification_note='Address pattern matched in document'
            )
            
        return MappedField(
            value=None,
            confidence=0.0,
            source='manual',
            verification_note='Address not found - manual review required'
        )
        
    def _map_city(self, fields: Dict, raw_text: str) -> MappedField:
        """Extract city"""
        # Try to extract from City, State ZIP pattern
        city_state_zip = fields.get('city_state_zip')
        if city_state_zip:
            parts = city_state_zip.split(',')
            if len(parts) >= 1:
                return MappedField(
                    value=parts[0].strip(),
                    confidence=0.75,
                    source='pdf_text',
                    verification_note='City from address block'
                )
                
        return MappedField(
            value=None,
            confidence=0.0,
            source='manual',
            verification_note='City not found - manual review required'
        )
        
    def _map_state(self, fields: Dict, raw_text: str) -> MappedField:
        """Extract state"""
        city_state_zip = fields.get('city_state_zip')
        if city_state_zip:
            # Look for 2-letter state code
            state_match = re.search(r',\s*([A-Z]{2})\s*\d', city_state_zip)
            if state_match:
                return MappedField(
                    value=state_match.group(1),
                    confidence=0.80,
                    source='pdf_text',
                    verification_note='State from address block'
                )
                
        return MappedField(
            value=None,
            confidence=0.0,
            source='manual',
            verification_note='State not found - manual review required'
        )
        
    def _map_zip_code(self, fields: Dict, raw_text: str) -> MappedField:
        """Extract ZIP code"""
        city_state_zip = fields.get('city_state_zip')
        if city_state_zip:
            zip_match = re.search(r'(\d{5}(?:-\d{4})?)', city_state_zip)
            if zip_match:
                return MappedField(
                    value=zip_match.group(1),
                    confidence=0.85,
                    source='pdf_text',
                    verification_note='ZIP from address block'
                )
                
        # Try to find any ZIP in raw text
        zip_pattern = r'\b(\d{5}(?:-\d{4})?)\b'
        match = re.search(zip_pattern, raw_text)
        if match:
            return MappedField(
                value=match.group(1),
                confidence=0.70,
                source='inferred',
                verification_note='ZIP found in document'
            )
            
        return MappedField(
            value=None,
            confidence=0.0,
            source='manual',
            verification_note='ZIP not found - manual review required'
        )
