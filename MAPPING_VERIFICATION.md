# Lien Automation - Field Mapping Guide

## Google Sheets Column Mapping

| Column | Field Name | Source | Notes |
|--------|------------|--------|-------|
| A | Site Id | Site configuration | 12=NYC ACRIS, 10=Cook County, 20=CA SOS |
| B | LienOrReceiveDate | PDF/Website extraction | Normalized to MM/DD/YYYY format |
| C | Amount | PDF extraction | $ and commas removed, stored as number |
| D | LeadType | Calculated | Always "Lien" for tax liens |
| E | LeadSource | Calculated | Always "777" |
| F | LiabilityType | Calculated | "IRS" for federal tax liens |
| G | BusinessPersonal | Classification | "Business" or "Personal" based on debtor name |
| H | Company | PDF extraction | Business name (if Business type) |
| I | FirstName | PDF extraction | First name (if Personal type) |
| J | LastName | PDF extraction | Last name (if Personal type) |
| K | Street | Address extraction | Street address |
| L | City | Address extraction | City name |
| M | State | Address extraction | State abbreviation |
| N | Zip | Address extraction | ZIP code |

## Mapping Logic by Site

### NYC ACRIS (Site ID: 12)
- **Source**: NYC ACRIS website + PDF documents
- **LiabilityType**: IRS
- **Date Source**: Document recording date
- **Business Detection**: INC, LLC, CORP, LTD, COMPANY keywords

### Cook County (Site ID: 10)
- **Source**: Cook County Recorder
- **LiabilityType**: IRS
- **Status**: 🔄 Planned implementation

### California SOS UCC (Site ID: 20)
- **Source**: CA Secretary of State UCC search
- **LiabilityType**: IRS
- **Date Source**: Filing date from search results
- **Business Detection**: INC, LLC, CORP, LTD, COMPANY keywords

## Data Flow

```
┌─────────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  County Website │───▶│ PDF Extract │───▶│ Field Mapper │───▶│ Google Sheet│
│  or PDF Source  │    │  (OCR/Text) │    │ (Standardize)│    │  (Output)   │
└─────────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
                                              │
                                              ▼
                                        ┌──────────────┐
                                        │   Deduplicate│
                                        │  (Site+Amount+Name)
                                        └──────────────┘
```

## Confidence Scoring

Each field has a confidence score (0.0-1.0):
- **High (≥0.85)**: Auto-processed to sheet
- **Medium (0.70-0.84)**: Flagged for review
- **Low (<0.70)**: Manual review required

## Deduplication Key

Records are deduplicated using:
`{SiteID}_{Amount}_{CompanyOrLastName}`

## Files Handling Mapping

| File | Purpose |
|------|---------|
| `src/field_mapper.py` | Core mapping logic |
| `src/sheets_integration.py` | Google Sheets output |
| `src/scrapers/*` | Site-specific extraction |
| `main.py` | Pipeline orchestration |

## Verified: Mapping is Accurate ✅

The existing implementation correctly maps to the Google Sheets format per the Mapping Guide.

### Test Results

**Test 1: Emmanuel Pacquiao (Personal Lead)**
- Site Id: 11 (Dallas County) ✅
- LienOrReceiveDate: Empty (not on doc) ✅
- Amount: 18313668 ($ and .00 removed) ✅
- LeadType: Lien ✅
- LeadSource: 777 ✅
- LiabilityType: IRS ✅
- BusinessPersonal: Personal ✅
- Company: Empty (Personal lead) ✅
- FirstName: Emmanuel ✅
- LastName: Pacquiao ✅
- Address fields: All correct ✅

**Test 2: Business Lead**
- BusinessPersonal: Business ✅
- Company: Populated ✅
- FirstName/LastName: Empty (Business lead) ✅

### Amount Formatting
- Removes `$` symbol
- Removes `,` commas  
- Removes `.00` decimal suffix for whole numbers
- Stores as clean integer string

### Business/Personal Logic
- **Personal**: First/LastName populated, Company empty
- **Business**: Company populated, First/LastName empty
- Detection based on keywords: INC, LLC, CORP, CORPORATION, LTD, COMPANY, ENTERPRISES, SERVICES, HOLDINGS, PARTNERSHIP
