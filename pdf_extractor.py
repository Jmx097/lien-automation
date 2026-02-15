"""
PDF Extractor Module
Handles multi-page PDF downloads and text extraction with OCR fallback
"""
import io
import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import requests
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)


@dataclass
class PDFPage:
    """Single page from PDF with extracted content"""
    page_number: int
    text: str
    images: List[bytes]
    ocr_text: Optional[str]


@dataclass
class ExtractedPDF:
    """Complete PDF extraction result"""
    filename: str
    pages: List[PDFPage]
    all_text: str
    is_searchable: bool


class PDFExtractor:
    """Extract text from PDFs with OCR fallback for scanned documents"""

    def __init__(self, temp_dir: str = "/tmp/lien_pdfs"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)

    def download_pdf(self, url: str, filename: Optional[str] = None) -> str:
        """Download PDF from URL to temp location"""
        if not filename:
            filename = f"lien_{hash(url)}.pdf"

        filepath = self.temp_dir / filename

        try:
            logger.info(f"Downloading PDF from {url}")
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info(f"PDF saved to {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to download PDF: {e}")
            raise

    def extract_text(self, pdf_path: str) -> ExtractedPDF:
        """Extract text from all pages of PDF"""
        logger.info(f"Extracting text from {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            pages: List[PDFPage] = []
            all_text_parts: List[str] = []
            is_searchable = False

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Try to get text directly (for searchable PDFs)
                text = page.get_text()

                if text.strip():
                    is_searchable = True
                    logger.debug(
                        f"Page {page_num + 1}: Extracted {len(text)} chars via text extraction"
                    )
                else:
                    # PDF is scanned image - use OCR
                    logger.info(
                        f"Page {page_num + 1}: No searchable text, using OCR"
                    )
                    text = self._ocr_page(page)

                # Extract images for potential additional processing
                images = self._extract_images(page)

                # Try OCR on images as additional source
                ocr_text = None
                if images and not text.strip():
                    ocr_text = self._ocr_images(images)

                pdf_page = PDFPage(
                    page_number=page_num + 1,
                    text=text,
                    images=images,
                    ocr_text=ocr_text,
                )

                pages.append(pdf_page)
                all_text_parts.append(text)
                if ocr_text:
                    all_text_parts.append(ocr_text)

            doc.close()

            all_text = "\n\n".join(all_text_parts)

            result = ExtractedPDF(
                filename=Path(pdf_path).name,
                pages=pages,
                all_text=all_text,
                is_searchable=is_searchable,
            )

            logger.info(
                f"Extracted {len(pages)} pages, total {len(all_text)} chars"
            )
            return result

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise

    def _ocr_page(self, page) -> str:
        """OCR a PDF page using PyMuPDF -> PIL -> Tesseract"""
        try:
            # Render page as image (2x zoom for better OCR)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")

            # Convert to PIL Image
            img = Image.open(io.BytesIO(img_data))

            # OCR with Tesseract
            text = pytesseract.image_to_string(img)

            logger.debug(f"OCR extracted {len(text)} chars")
            return text

        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

    def _extract_images(self, page) -> List[bytes]:
        """Extract embedded images from PDF page"""
        images: List[bytes] = []
        try:
            image_list = page.get_images()
            for _, img in enumerate(image_list, start=1):
                xref = img[0]
                base_image = page.parent.extract_image(xref)
                image_bytes = base_image["image"]
                images.append(image_bytes)
        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")
        return images

    def _ocr_images(self, images: List[bytes]) -> str:
        """OCR list of image bytes"""
        texts: List[str] = []
        for img_bytes in images:
            try:
                img = Image.open(io.BytesIO(img_bytes))
                text = pytesseract.image_to_string(img)
                texts.append(text)
            except Exception as e:
                logger.warning(f"Image OCR failed: {e}")
        return "\n".join(texts)

    def extract_from_url(self, url: str) -> ExtractedPDF:
        """Download and extract PDF in one step"""
        pdf_path = self.download_pdf(url)
        return self.extract_text(pdf_path)


class FieldExtractor:
    """
    Extract specific fields from PDF text and map them to the
    Excel export schema (Site Id, LienOrReceiveDate, Amount, LeadType,
    LeadSource, LiabilityType, BusinessPersonal, Company, FirstName,
    LastName, Street, City, State, Zip).
    """

    # Regex helpers
    AMOUNT_PATTERNS = [
        # Per mapping guide: amount shown as "Total" on the doc
        r"TOTAL\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})",
        r"AMOUNT\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})",
        r"LIEN\s+AMOUNT\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})",
        # Fallback generic dollar amount
        r"\$?([\d,]+\.\d{2})",
    ]

    TAXPAYER_NAME_PATTERNS = [
        # Use double-quoted raw strings so apostrophes inside the class are safe
        r"NAME\s+OF\s+TAXPAYER\s*[:\-]?\s*([\w\s\-',.]+)",
        r"TAXPAYER\s*[:\-]?\s*([\w\s\-',.]+)",
    ]

    ADDRESS_PATTERN = (
        r"(\d+\s+[\w\s]+"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|"
        r"Plaza|Plz|Suite|Ste|Floor|Fl)\.?)"
    )

    CITY_STATE_ZIP_PATTERN = (
        r"([A-Za-z\s]+),?\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)"
    )

    # Fallback text-based lien date (used only when no recorder/results-table date)
    LIEN_DATE_TEXT_PATTERNS = [
        r"DATE\s+OF\s+LIEN\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"LIEN\s+DATE\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"FILED\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]

    BUSINESS_KEYWORDS = [
        " INC",
        " LLC",
        " COMPANY",
        " CO ",
        " SERVICE",
        " SERVICES",
        " SOLUTION",
        " SOLUTIONS",
        " LTD",
        " LP ",
        " LLP ",
        " PC ",
        " PLLC",
    ]

    def extract_amount(self, pdf_text: str) -> Optional[str]:
        """Extract the Total amount per mapping guide."""
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, pdf_text, flags=re.IGNORECASE)
            if match:
                value = match.group(1).replace(",", "").strip()
                return value
        return None

    def extract_taxpayer_name_raw(self, pdf_text: str) -> Optional[str]:
        """Extract raw Name of Taxpayer string."""
        for pattern in self.TAXPAYER_NAME_PATTERNS:
            match = re.search(pattern, pdf_text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def extract_address_components(
        self, pdf_text: str
    ) -> Dict[str, Optional[str]]:
        """Extract Street, City, State, Zip (5-digit) from the document."""
        street = None
        city = None
        state = None
        zip5 = None

        street_match = re.search(self.ADDRESS_PATTERN, pdf_text, flags=re.IGNORECASE)
        if street_match:
            street = street_match.group(1).strip()

        csz_match = re.search(
            self.CITY_STATE_ZIP_PATTERN, pdf_text, flags=re.IGNORECASE
        )
        if csz_match:
            city = csz_match.group(1).strip()
            state = csz_match.group(2).strip()
            raw_zip = csz_match.group(3).strip()
            # Only first 5 characters of ZIP even if ZIP+4 is present
            zip5 = raw_zip[:5]

        return {
            "Street": street,
            "City": city,
            "State": state,
            "Zip": zip5,
        }

    def extract_lead_type(self, pdf_text: str) -> Optional[str]:
        """
        Determine LeadType (Lien vs Release) based on document title/top text.

        - Look for "Certificate of Release", "Release of Federal Tax Lien" → Release
        - Look for "Notice of Federal Tax Lien" → Lien
        """
        text_upper = pdf_text.upper()

        if "CERTIFICATE OF RELEASE" in text_upper or "RELEASE OF FEDERAL TAX LIEN" in text_upper:
            return "Release"
        if "NOTICE OF FEDERAL TAX LIEN" in text_upper or "FEDERAL TAX LIEN" in text_upper:
            return "Lien"

        return None

    def _looks_like_person_name(self, name: str) -> bool:
        """
        Heuristic: 'First Last' or 'First M Last' style, no strong business keywords.
        """
        tokens = [t for t in name.replace(",", " ").split() if t]
        if len(tokens) < 2 or len(tokens) > 4:
            return False

        # If it contains typical business keywords, don't treat as a pure person name
        upper_name = " " + name.upper() + " "
        if any(kw in upper_name for kw in self.BUSINESS_KEYWORDS):
            return False

        # Basic capitalization heuristic
        cap_tokens = [t for t in tokens if t[0].isalpha()]
        if len(cap_tokens) >= 2:
            return True

        return False

    def classify_business_personal_and_names(
        self, taxpayer_name_raw: Optional[str], pdf_text: str
    ) -> Dict[str, Optional[str]]:
        """
        Decide BusinessPersonal (Business/Personal) and populate
        Company / FirstName / LastName per mapping guide.
        """
        if not taxpayer_name_raw:
            return {
                "BusinessPersonal": None,
                "Company": None,
                "FirstName": None,
                "LastName": None,
            }

        name = " ".join(t for t in taxpayer_name_raw.replace("  ", " ").split())
        upper_name = " " + name.upper() + " "
        text_upper = pdf_text.upper()

        is_business = False

        # Keyword-based business hints (INC, LLC, Company, Solutions, etc.)
        if any(kw in upper_name for kw in self.BUSINESS_KEYWORDS):
            is_business = True

        # Kind of Tax shows 941 is another indicator of Business (per guide)
        if " 941" in text_upper or "FORM 941" in text_upper:
            is_business = True

        looks_like_person = self._looks_like_person_name(name)

        business_personal: Optional[str] = None
        company: Optional[str] = None
        first_name: Optional[str] = None
        last_name: Optional[str] = None

        if is_business and not looks_like_person:
            business_personal = "Business"
            company = name
        elif looks_like_person and not is_business:
            business_personal = "Personal"
            # Parse First / Last from pattern "First [Middle] Last"
            tokens = [t for t in name.replace(",", " ").split() if t]
            if len(tokens) >= 2:
                first_name = tokens[0]
                last_name = tokens[-1]
        else:
            # Ambiguous cases – default to Personal with best-effort split
            business_personal = "Personal"
            tokens = [t for t in name.replace(",", " ").split() if t]
            if len(tokens) >= 2:
                first_name = tokens[0]
                last_name = tokens[-1]

        return {
            "BusinessPersonal": business_personal,
            "Company": company,
            "FirstName": first_name,
            "LastName": last_name,
        }

    def extract_lien_or_receive_date(
        self,
        pdf_text: str,
        recorder_stamp_date: Optional[str],
        results_table_filing_date: Optional[str],
    ) -> Optional[str]:
        """
        LienOrReceiveDate mapping per guide:

        - Prefer recorder stamp date on the document when present.
        - Otherwise use results table filing date from the website.
        - Never use the IRS prepared/signed date in the body text.
        - Only fall back to text patterns if both are missing.
        """
        if recorder_stamp_date:
            return recorder_stamp_date.strip()

        if results_table_filing_date:
            return results_table_filing_date.strip()

        # Fallback: scan text, but try to avoid "PREPARED" or "PREPARER" contexts
        for pattern in self.LIEN_DATE_TEXT_PATTERNS:
            for match in re.finditer(pattern, pdf_text, flags=re.IGNORECASE):
                span_start = match.start()
                window_start = max(0, span_start - 80)
                context = pdf_text[window_start:span_start].upper()
                if "PREPARED" in context or "PREPARER" in context:
                    continue
                return match.group(1).strip()

        return None

    def extract_raw_fields(self, pdf_text: str) -> Dict[str, Any]:
        """
        Optional: keep a simple raw-field extraction similar to the original,
        in case callers want the underlying values.
        """
        raw: Dict[str, Any] = {}

        amount = self.extract_amount(pdf_text)
        if amount is not None:
            raw["amount"] = amount

        taxpayer_name = self.extract_taxpayer_name_raw(pdf_text)
        if taxpayer_name is not None:
            raw["taxpayer_name"] = taxpayer_name

        addr = self.extract_address_components(pdf_text)
        raw.update(
            {
                "address_street": addr.get("Street"),
                "address_city": addr.get("City"),
                "address_state": addr.get("State"),
                "address_zip": addr.get("Zip"),
            }
        )

        # Optional SSN / EIN patterns (not part of Excel schema but may be useful)
        ssn_match = re.search(r"(\d{3}-\d{2}-\d{4}|XXX-XX-\d{4})", pdf_text)
        if ssn_match:
            raw["ssn"] = ssn_match.group(1)

        ein_match = re.search(r"(\d{2}-\d{7})", pdf_text)
        if ein_match:
            raw["ein"] = ein_match.group(1)

        return raw

    def build_export_row(
        self,
        pdf_text: str,
        site_id: Optional[str] = None,
        liability_type: Optional[str] = None,
        recorder_stamp_date: Optional[str] = None,
        results_table_filing_date: Optional[str] = None,
        lead_source: str = "777",
    ) -> Dict[str, Optional[str]]:
        """
        Build a dict that matches the Excel export columns exactly:

        Site Id, LienOrReceiveDate, Amount, LeadType, LeadSource,
        LiabilityType, BusinessPersonal, Company, FirstName, LastName,
        Street, City, State, Zip.
        """
        amount = self.extract_amount(pdf_text)
        taxpayer_name_raw = self.extract_taxpayer_name_raw(pdf_text)
        addr = self.extract_address_components(pdf_text)
        lead_type = self.extract_lead_type(pdf_text)
        bp = self.classify_business_personal_and_names(
            taxpayer_name_raw, pdf_text
        )
        lien_or_receive_date = self.extract_lien_or_receive_date(
            pdf_text=pdf_text,
            recorder_stamp_date=recorder_stamp_date,
            results_table_filing_date=results_table_filing_date,
        )

        export_row: Dict[str, Optional[str]] = {
            "Site Id": site_id,
            "LienOrReceiveDate": lien_or_receive_date,
            "Amount": amount,
            "LeadType": lead_type,
            "LeadSource": lead_source,  # always 777 per mapping guide
            "LiabilityType": liability_type,  # from Lien Sites sheet / caller
            "BusinessPersonal": bp.get("BusinessPersonal"),
            "Company": bp.get("Company"),
            "FirstName": bp.get("FirstName"),
            "LastName": bp.get("LastName"),
            "Street": addr.get("Street"),
            "City": addr.get("City"),
            "State": addr.get("State"),
            "Zip": addr.get("Zip"),
        }

        return export_row


def process_pdf(
    url: Optional[str] = None,
    local_path: Optional[str] = None,
    *,
    site_id: Optional[str] = None,
    liability_type: Optional[str] = None,
    recorder_stamp_date: Optional[str] = None,
    results_table_filing_date: Optional[str] = None,
    lead_source: str = "777",
) -> Dict[str, Any]:
    """
    Process PDF and return both:
      - export_row: dict that matches the Excel export schema
      - raw_fields: additional raw parsed values
      - all_text / is_searchable / page_count: diagnostic info

    Parameters
    ----------
    url : Optional[str]
        URL to download the PDF from.
    local_path : Optional[str]
        Path to a local PDF file.
    site_id : Optional[str]
        Site Id (not on the doc, from Lien Sites sheet or calling code).
    liability_type : Optional[str]
        LiabilityType ("IRS" or "State"), site-specific from Lien Sites sheet.
    recorder_stamp_date : Optional[str]
        Date read from the recorder stamp on the document (preferred).
    results_table_filing_date : Optional[str]
        Filing date from the website results table (used when no stamp).
    lead_source : str
        LeadSource value, defaults to "777" per mapping guide.
    """
    extractor = PDFExtractor()
    field_extractor = FieldExtractor()

    if url:
        pdf_result = extractor.extract_from_url(url)
    elif local_path:
        pdf_result = extractor.extract_text(local_path)
    else:
        raise ValueError("Must provide either url or local_path")

    pdf_text = pdf_result.all_text

    export_row = field_extractor.build_export_row(
        pdf_text=pdf_text,
        site_id=site_id,
        liability_type=liability_type,
        recorder_stamp_date=recorder_stamp_date,
        results_table_filing_date=results_table_filing_date,
        lead_source=lead_source,
    )

    raw_fields = field_extractor.extract_raw_fields(pdf_text)

    return {
        "export_row": export_row,
        "raw_fields": raw_fields,
        "all_text": pdf_result.all_text,
        "is_searchable": pdf_result.is_searchable,
        "page_count": len(pdf_result.pages),
    }
