"""
Accuracy Verifier Module
Validates extracted fields against known patterns and flags low-confidence extractions
"""

import re
import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass
from field_mapper import MappedRecord, MappedField

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of field validation"""
    field_name: str
    value: str
    is_valid: bool
    confidence: float
    issues: List[str]
    suggestions: List[str]


@dataclass
class VerificationReport:
    """Complete verification report for a record"""
    record_id: str
    overall_confidence: float
    validation_results: List[ValidationResult]
    can_auto_process: bool
    requires_manual_review: bool
    flagged_fields: List[str]
    recommendations: List[str]


class AccuracyVerifier:
    """Verify accuracy of extracted lien data with confidence scoring"""
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.70
    LOW_CONFIDENCE = 0.50
    
    # Validation patterns
    PATTERNS = {
        'ssn': r'^\d{3}-\d{2}-\d{4}$|^XXX-XX-\d{4}$',
        'ein': r'^\d{2}-\d{7}$|^XX-XXXXXXX$',
        'zip': r'^\d{5}(-\d{4})?$',
        'amount': r'^\d+$',  # Should be numeric without decimals for storage
        'date': r'^\d{2}/\d{2}/\d{4}$',
        'state': r'^[A-Z]{2}$',
    }
    
    # Known values for validation
    VALID_LIABILITY_TYPES = ['IRS', 'State', 'Local']
    VALID_LEAD_TYPES = ['Lien', 'Release', 'UCC', 'Mechanic']
    VALID_BUSINESS_PERSONAL = ['Business', 'Personal', 'Unknown']
    
    def __init__(self):
        self.validation_issues = []
        
    def verify_record(self, record: MappedRecord) -> VerificationReport:
        """Complete verification of a mapped record"""
        logger.info(f"Verifying record with site_id {record.site_id}")
        
        results = []
        flagged_fields = []
        recommendations = []
        
        # Verify each field
        field_checks = [
            ('lien_or_receive_date', record.lien_or_receive_date, self._validate_date),
            ('amount', record.amount, self._validate_amount),
            ('lead_type', record.lead_type, self._validate_lead_type),
            ('lead_source', record.lead_source, self._validate_lead_source),
            ('liability_type', record.liability_type, self._validate_liability_type),
            ('business_personal', record.business_personal, self._validate_business_personal),
            ('company', record.company, self._validate_company),
            ('first_name', record.first_name, self._validate_name),
            ('last_name', record.last_name, self._validate_name),
            ('street', record.street, self._validate_street),
            ('city', record.city, self._validate_city),
            ('state', record.state, self._validate_state),
            ('zip_code', record.zip_code, self._validate_zip),
        ]
        
        for field_name, field_data, validator in field_checks:
            result = validator(field_name, field_data)
            results.append(result)
            
            if not result.is_valid or result.confidence < self.MEDIUM_CONFIDENCE:
                flagged_fields.append(field_name)
                
            if result.suggestions:
                recommendations.extend(result.suggestions)
                
        # Calculate overall confidence
        overall_confidence = sum(r.confidence for r in results) / len(results)
        
        # Determine if record can be auto-processed
        can_auto_process = (
            overall_confidence >= self.HIGH_CONFIDENCE and
            len(flagged_fields) <= 2 and  # Allow 2 minor issues
            not any(r.confidence < self.LOW_CONFIDENCE for r in results)
        )
        
        report = VerificationReport(
            record_id=f"{record.site_id}_{record.lien_or_receive_date.value or 'unknown'}",
            overall_confidence=overall_confidence,
            validation_results=results,
            can_auto_process=can_auto_process,
            requires_manual_review=not can_auto_process,
            flagged_fields=flagged_fields,
            recommendations=list(set(recommendations))  # Remove duplicates
        )
        
        logger.info(f"Verification complete: confidence={overall_confidence:.2f}, "
                   f"can_auto_process={can_auto_process}")
        
        return report
        
    def _create_result(self, field_name: str, field: MappedField, 
                       is_valid: bool, issues: List[str], 
                       suggestions: List[str]) -> ValidationResult:
        """Create validation result with adjusted confidence"""
        # Adjust confidence based on validation
        adjusted_confidence = field.confidence
        
        if not is_valid:
            adjusted_confidence *= 0.5  # Reduce confidence for invalid fields
            
        if issues:
            adjusted_confidence *= 0.9  # Slight reduction for issues
            
        return ValidationResult(
            field_name=field_name,
            value=field.value or '',
            is_valid=is_valid,
            confidence=adjusted_confidence,
            issues=issues,
            suggestions=suggestions
        )
        
    def _validate_date(self, name: str, field: MappedField) -> ValidationResult:
        """Validate date format"""
        issues = []
        suggestions = []
        
        if not field.value:
            return self._create_result(name, field, False, 
                ['Date is missing'], ['Check PDF for filing date'])
            
        if not re.match(self.PATTERNS['date'], field.value):
            issues.append(f'Date format invalid: {field.value}')
            suggestions.append('Expected format: MM/DD/YYYY')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_amount(self, name: str, field: MappedField) -> ValidationResult:
        """Validate amount"""
        issues = []
        suggestions = []
        
        if not field.value:
            return self._create_result(name, field, False,
                ['Amount is missing'], ['Check PDF for lien amount'])
            
        # Should be numeric
        try:
            amount = int(field.value)
            if amount < 1000:
                issues.append(f'Amount seems low: ${amount}')
                suggestions.append('Verify this is the total lien amount')
            elif amount > 100000000:  # $100M
                issues.append(f'Amount seems very high: ${amount}')
                suggestions.append('Verify decimal placement')
        except ValueError:
            issues.append(f'Amount is not numeric: {field.value}')
            suggestions.append('Remove any non-numeric characters')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_lead_type(self, name: str, field: MappedField) -> ValidationResult:
        """Validate lead type"""
        issues = []
        suggestions = []
        
        if field.value not in self.VALID_LEAD_TYPES:
            issues.append(f'Unknown lead type: {field.value}')
            suggestions.append(f'Expected one of: {", ".join(self.VALID_LEAD_TYPES)}')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_lead_source(self, name: str, field: MappedField) -> ValidationResult:
        """Validate lead source is 777"""
        issues = []
        suggestions = []
        
        if field.value != '777':
            issues.append(f'Lead source is not 777: {field.value}')
            suggestions.append('Lead source should always be 777 per Mapping Guide')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_liability_type(self, name: str, field: MappedField) -> ValidationResult:
        """Validate liability type"""
        issues = []
        suggestions = []
        
        if field.value not in self.VALID_LIABILITY_TYPES:
            issues.append(f'Unknown liability type: {field.value}')
            suggestions.append(f'Expected one of: {", ".join(self.VALID_LIABILITY_TYPES)}')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_business_personal(self, name: str, field: MappedField) -> ValidationResult:
        """Validate business/personal classification"""
        issues = []
        suggestions = []
        
        if field.value not in self.VALID_BUSINESS_PERSONAL:
            issues.append(f'Unknown classification: {field.value}')
            suggestions.append(f'Expected: Business, Personal, or Unknown')
            
        if field.value == 'Unknown':
            issues.append('Could not determine Business/Personal')
            suggestions.append('Review taxpayer name for business indicators (INC, LLC, etc.)')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_company(self, name: str, field: MappedField) -> ValidationResult:
        """Validate company name (only required for Business)"""
        issues = []
        suggestions = []
        
        # If this is a business record, company should have value
        # Note: We don't have context here, so basic validation only
        
        return self._create_result(name, field, True, issues, suggestions)
        
    def _validate_name(self, name: str, field: MappedField) -> ValidationResult:
        """Validate first/last name"""
        issues = []
        suggestions = []
        
        if field.value:
            # Check for suspicious patterns
            if len(field.value) < 2:
                issues.append(f'Name seems too short: {field.value}')
                suggestions.append('Verify name extraction from taxpayer field')
                
            if re.search(r'\d', field.value):
                issues.append(f'Name contains numbers: {field.value}')
                suggestions.append('Remove numeric characters from name')
                
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_street(self, name: str, field: MappedField) -> ValidationResult:
        """Validate street address"""
        issues = []
        suggestions = []
        
        if not field.value:
            issues.append('Street address is missing')
            suggestions.append('Check PDF for address block')
        else:
            # Should have street number
            if not re.search(r'^\d+', field.value):
                issues.append('Street address may be missing number')
                suggestions.append('Verify complete address extraction')
                
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_city(self, name: str, field: MappedField) -> ValidationResult:
        """Validate city"""
        issues = []
        suggestions = []
        
        if not field.value:
            issues.append('City is missing')
            suggestions.append('Check address block in PDF')
        elif len(field.value) < 2:
            issues.append(f'City name seems too short: {field.value}')
            suggestions.append('Verify city extraction')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_state(self, name: str, field: MappedField) -> ValidationResult:
        """Validate state code"""
        issues = []
        suggestions = []
        
        if not field.value:
            issues.append('State is missing')
            suggestions.append('Check address block in PDF')
        elif not re.match(self.PATTERNS['state'], field.value):
            issues.append(f'State format invalid: {field.value}')
            suggestions.append('Expected 2-letter state code (e.g., NY, CA, IL)')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)
        
    def _validate_zip(self, name: str, field: MappedField) -> ValidationResult:
        """Validate ZIP code"""
        issues = []
        suggestions = []
        
        if not field.value:
            issues.append('ZIP code is missing')
            suggestions.append('Check address block in PDF')
        elif not re.match(self.PATTERNS['zip'], field.value):
            issues.append(f'ZIP format invalid: {field.value}')
            suggestions.append('Expected 5-digit or ZIP+4 format')
            
        return self._create_result(name, field, len(issues) == 0, issues, suggestions)


def verify_records(records: List[MappedRecord]) -> List[Tuple[MappedRecord, VerificationReport]]:
    """Verify multiple records and return with reports"""
    verifier = AccuracyVerifier()
    results = []
    
    for record in records:
        report = verifier.verify_record(record)
        results.append((record, report))
        
    return results
