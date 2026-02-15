# Federal Tax Lien Automation

Automated extraction of Federal Tax Lien data from county recorder websites. Scrapes NYC ACRIS (and soon Cook County, CA SOS), extracts PDF data with OCR fallback, maps to standardized format, and writes to Google Sheets.

## Architecture

```
src/
├── browser_automation.py    # Playwright-based web scraping
├── pdf_extractor.py         # PyMuPDF + Tesseract OCR
├── field_mapper.py          # Map extracted data to standard format
├── accuracy_verifier.py     # Confidence scoring & validation
├── sheets_integration.py    # Google Sheets API integration
├── dedupe_utility.py        # Duplicate detection & removal
├── ai_classifier.py         # Business/Personal classification
├── config.py                # Site configuration management
└── utils.py                 # Logging & utilities

config/
└── sites.json               # Site definitions

main.py                      # Cloud Function entry point
requirements.txt             # Python dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt

# Install Tesseract OCR (system dependency)
# macOS: brew install tesseract
# Ubuntu: apt-get install tesseract-ocr
```

### 2. Configure Environment

```bash
export SHEETS_ID="your-google-sheet-id"
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
```

### 3. Run Locally

```bash
python main.py
```

### 4. Deploy to Google Cloud Functions

```bash
gcloud functions deploy lien_extraction \
    --runtime python311 \
    --trigger-http \
    --entry-point main \
    --memory 1GiB \
    --timeout 300s \
    --set-env-vars SHEETS_ID=your-sheet-id
```

## API Usage

### Request

```bash
curl -X POST https://your-function-url \
  -H "Content-Type: application/json" \
  -d '{
    "sites": ["12"],
    "max_results": 10
  }'
```

### Response

```json
{
  "success": true,
  "timestamp": "2024-02-15T12:00:00",
  "sites_processed": 1,
  "total_records_found": 5,
  "total_records_written": 4,
  "sheet_url": "https://docs.google.com/spreadsheets/d/.../edit",
  "results": [...]
}
```

## Supported Sites

| Site ID | Name | Status |
|---------|------|--------|
| 12 | NYC ACRIS | ✅ Implemented |
| 10 | Cook County | 🔄 Planned |
| 20 | CA SOS | 🔄 Planned |

## Data Format

Records are mapped to the following Google Sheets columns:

| Column | Field | Source |
|--------|-------|--------|
| A | Site Id | Site configuration |
| B | LienOrReceiveDate | Recorder stamp → Results table → Text extraction |
| C | Amount | "Total" field from PDF |
| D | LeadType | "Lien" or "Release" |
| E | LeadSource | Always "777" |
| F | LiabilityType | "IRS" or "State" |
| G | BusinessPersonal | Business keywords / Form 941 detection |
| H | Company | Business name (if Business) |
| I | FirstName | First name (if Personal) |
| J | LastName | Last name (if Personal) |
| K | Street | Address extraction |
| L | City | Address extraction |
| M | State | Address extraction |
| N | Zip | Address extraction |

## Confidence Scoring

Records are validated with confidence thresholds:
- **High (≥0.85)**: Auto-processed
- **Medium (0.70-0.84)**: Flagged for review
- **Low (<0.70)**: Manual review required

## Development

### Running Tests

```bash
# Test specific site
python -c "from main import main; from unittest.mock import Mock; print(main(Mock()))"
```

### Adding a New Site

1. Add site to `config/sites.json`
2. Implement scraper in `src/browser_automation.py`
3. Add site-specific field mapping in `src/field_mapper.py`

## License

Private - For client use only
