"""
PDF Extractor Module
Handles multi-page PDF downloads and text extraction with OCR fallback
"""

import io
import re
import logging
from typing import List, Optional, Dict
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
            
            with open(filepath, 'wb') as f:
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
            pages = []
            all_text_parts = []
            is_searchable = False
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Try to get text directly (for searchable PDFs)
                text = page.get_text()
                
                if text.strip():
                    is_searchable = True
                    logger.debug(f"Page {page_num + 1}: Extracted {len(text)} chars via text extraction")
                else:
                    # PDF is scanned image - use OCR
                    logger.info(f"Page {page_num + 1}: No searchable text, using OCR")
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
                    ocr_text=ocr_text
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
                is_searchable=is_searchable
            )
            
            logger.info(f"Extracted {len(pages)} pages, total {len(all_text)} chars")
            return result
            
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise
            
    def _ocr_page(self, page) -> str:
        """OCR a PDF page using PyMuPDF -> PIL -> Tesseract"""
        try:
            # Render page as image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
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
        images = []
        try:
            image_list = page.get_images()
            for img_index, img in enumerate(image_list, start=1):
                xref = img[0]
                base_image = page.parent.extract_image(xref)
                image_bytes = base_image["image"]
                images.append(image_bytes)
        except Exception as e:
            logger.warning(f"Image extraction failed: {e}")
        return images
        
    def _ocr_images(self, images: List[bytes]) -> str:
        """OCR list of image bytes"""
        texts = []
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
    """Extract specific fields from PDF text using patterns"""
    
    # IRS Federal Tax Lien patterns
    PATTERNS = {
        'amount': [
            r'\$?([\d,]+\.\d{2})',  # Generic dollar amount
            r'AMOUNT\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})',
            r'LIEN\s+AMOUNT\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})',
            r'TOTAL\s*[:\-]?\s*\$?([\d,]+\.?\d{0,2})',
        ],
        'taxpayer_name': [
            r'NAME\s+OF\s+TAXPAYER\s*[:\-]?\s*([\w\s\-\.',.]+)',
            r'TAXPAYER\s*[:\-]?\s*([\w\s\-\.',.]+)',
        ],
        'address': [
            r'(\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Plaza|Plz|Suite|Ste|Floor|Fl)\.?)',
        ],
        'city_state_zip': [
            r'([A-Za-z\s]+),?\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)',
        ],
        'lien_date': [
            r'DATE\s+OF\s+LIEN\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'LIEN\s+DATE\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'FILED\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        ],
        'ssn': [
            r'(\d{3}-\d{2}-\d{4})',
            r'(XXX-XX-\d{4})',
        ],
        'ein': [
            r'(\d{2}-\d{7})',
        ],
    }
    
    def __init__(self):
        self.extractor = PDFExtractor()
        
    def extract_all_fields(self, pdf_text: str) -> Dict:
        """Extract all known fields from PDF text"""
        results = {}
        
        for field_name, patterns in self.PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, pdf_text, re.IGNORECASE)
                if matches:
                    # Take the first/best match
                    best_match = matches[0]
                    if isinstance(best_match, tuple):
                        best_match = ' '.join(best_match)
                    results[field_name] = best_match.strip()
                    break
                    
        return results


def process_pdf(url: Optional[str] = None, local_path: Optional[str] = None) -> Dict:
    """Process PDF and extract all fields"""
    extractor = PDFExtractor()
    field_extractor = FieldExtractor()
    
    if url:
        pdf_result = extractor.extract_from_url(url)
    elif local_path:
        pdf_result = extractor.extract_text(local_path)
    else:
        raise ValueError("Must provide either url or local_path")
        
    fields = field_extractor.extract_all_fields(pdf_result.all_text)
    
    return {
        'fields': fields,
        'all_text': pdf_result.all_text,
        'is_searchable': pdf_result.is_searchable,
        'page_count': len(pdf_result.pages)
    }
