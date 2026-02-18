#!/usr/bin/env python3
"""
Test script to verify field mapping against example data
"""

import sys
sys.path.insert(0, '/home/ubuntu/.openclaw/workspace/lien-automation/src')

from field_mapper import FieldMapper, MappedRecord

def test_emmanuel_pacquiao_mapping():
    """Test mapping with the provided example"""
    
    # Example data from the CSV
    extracted_fields = {
        'taxpayer_name': 'Emmanuel Pacquiao',
        'address': '10886 Wilshire Boulevard Floor 10',
        'city_state_zip': 'Los Angeles, CA 90024',
        # Date not on doc - will be empty
        # Amount from Total section
        'amount': '$18,313,668.00'
    }
    
    raw_text = """
    Notice of Federal Tax Lien
    Name of Taxpayer: Emmanuel Pacquiao
    Address: 10886 Wilshire Boulevard Floor 10
    Los Angeles, CA 90024
    Total: $18,313,668.00
    """
    
    # Create mapper for Dallas County (Site ID 11)
    mapper = FieldMapper('dallas_county')
    
    # Map the record
    record = mapper.map_record(extracted_fields, raw_text)
    
    # Convert to row
    row = record.to_row()
    
    print("=" * 60)
    print("MAPPING TEST: Emmanuel Pacquiao Example")
    print("=" * 60)
    
    # Expected values from example
    expected = {
        'Site Id': '11',
        'LienOrReceiveDate': '',  # Empty - not on doc
        'Amount': '18313668',  # $ and commas removed
        'LeadType': 'Lien',
        'LeadSource': '777',
        'LiabilityType': 'IRS',
        'BusinessPersonal': 'Personal',
        'Company': '',  # Empty for Personal
        'FirstName': 'Emmanuel',
        'LastName': 'Pacquiao',
        'Street': '10886 Wilshire Boulevard Floor 10',
        'City': 'Los Angeles',
        'State': 'CA',
        'Zip': '90024'
    }
    
    headers = [
        'Site Id', 'LienOrReceiveDate', 'Amount', 'LeadType', 'LeadSource',
        'LiabilityType', 'BusinessPersonal', 'Company', 'FirstName', 'LastName',
        'Street', 'City', 'State', 'Zip'
    ]
    
    all_pass = True
    for i, header in enumerate(headers):
        actual = row[i] if row[i] is not None else ''
        exp = expected[header]
        status = "✅ PASS" if actual == exp else "❌ FAIL"
        if actual != exp:
            all_pass = False
        print(f"{status} {header:20} | Expected: '{exp}' | Got: '{actual}'")
    
    print("=" * 60)
    print(f"OVERALL: {'✅ ALL TESTS PASSED' if all_pass else '❌ SOME TESTS FAILED'}")
    print("=" * 60)
    
    return all_pass


def test_business_mapping():
    """Test mapping with a business example"""
    
    extracted_fields = {
        'taxpayer_name': 'ACME CONSTRUCTION INC',
        'address': '123 Main Street Suite 100',
        'city_state_zip': 'Dallas, TX 75201',
        'lien_date': '02/15/2024',
        'amount': '$50,000.00'
    }
    
    raw_text = """
    Notice of Federal Tax Lien
    Name of Taxpayer: ACME CONSTRUCTION INC
    Address: 123 Main Street Suite 100
    Dallas, TX 75201
    Date: 02/15/2024
    Total: $50,000.00
    """
    
    mapper = FieldMapper('dallas_county')
    record = mapper.map_record(extracted_fields, raw_text)
    row = record.to_row()
    
    print("\n" + "=" * 60)
    print("MAPPING TEST: Business Example (ACME CONSTRUCTION INC)")
    print("=" * 60)
    
    # For Business: Company populated, First/Last empty
    checks = [
        ('BusinessPersonal', row[6], 'Business'),
        ('Company', row[7], 'ACME CONSTRUCTION INC'),
        ('FirstName', row[8], ''),  # Should be empty
        ('LastName', row[9], ''),   # Should be empty
    ]
    
    all_pass = True
    for field, actual, expected in checks:
        actual = actual if actual is not None else ''
        status = "✅ PASS" if actual == expected else "❌ FAIL"
        if actual != expected:
            all_pass = False
        print(f"{status} {field:20} | Expected: '{expected}' | Got: '{actual}'")
    
    print("=" * 60)
    print(f"OVERALL: {'✅ ALL TESTS PASSED' if all_pass else '❌ SOME TESTS FAILED'}")
    print("=" * 60)
    
    return all_pass


if __name__ == "__main__":
    test1 = test_emmanuel_pacquiao_mapping()
    test2 = test_business_mapping()
    
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    if test1 and test2:
        print("✅ ALL MAPPING TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
