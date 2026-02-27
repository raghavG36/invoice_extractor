"""
Pipeline B: Deterministic extraction using OCR + regex rules.
No LLM; structured patterns for invoice fields.
"""
import re
import logging
from pathlib import Path
from typing import Optional

from invoice_extractor.config import REQUIRED_FIELDS

# Reuse Pipeline A OCR (pytesseract) to avoid duplicate code; no LLM
from invoice_extractor.pipeline_a.llm_extractor import run_ocr

logger = logging.getLogger(__name__)


# Common patterns (generic; work across locales/formats)
PATTERNS = {
    "invoice_number": [
    r"^.*\b(?:invoice|factura|rechnung)\b.*?(?:no\.?|nr\.?|#)\s*[:\-]?\s*([A-Z0-9\-\/]{4,})",
],
    "invoice_date": [
    r"\b(?:invoice\s+date|date|datum|data)\b\s*[:\-]?\s*(\d{4}[./\-]\d{2}[./\-]\d{2})",
    r"\b(?:invoice\s+date|date|datum|data)\b\s*[:\-]?\s*(\d{2}[./\-]\d{2}[./\-]\d{4})",
],
    "seller_tax_id": [
    r"\b(?:seller|vendor|from)\b.*?(?:vat|tax\s*id|tin)\s*[:\-]?\s*([A-Z0-9\- ]{8,})",
    r"\bvat\s*[:\-]?\s*([A-Z]{2}\s?\d{8,12})",
],
    "client_tax_id": [
    r"\b(?:buyer|client|customer|bill\s+to)\b.*?(?:vat|tax\s*id|tin)\s*[:\-]?\s*([A-Z0-9\- ]{8,})",
],
   "net_worth": [
    r"\b(?:subtotal|net\s+amount|netto)\b\s*[:\-]?\s*([\d,.]+\d{2})"
],
    "vat": [
    r"\b(?:vat|tax)\b\s*[:\-]?\s*([\d,.]+\d{2})"
],
   "gross_worth": [
    r"\b(?  :total\s+amount|amount\s+due|gross|brutto|to\s+pay)\b\s*[:\-]?\s*([\d,.]+\d{2})"
],
}


def _first_match(text: str, patterns: list) -> Optional[str]:
    """Return first regex group match from text, cleaned."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip() if m.lastindex else None
    return None


def _parse_number(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.,\-]", "", s.replace(" ", ""))
    cleaned = cleaned.replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _extract_names_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    """Heuristic: first block often seller; look for 'sold to' / 'client' for buyer."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    seller = None
    client = None
    for i, line in enumerate(lines):
        if re.search(r"(sold\s+to|client|buyer|customer|odbiorca|nabywca)\s*[:\s]*", line, re.I):
            # Next line or rest of line might be client name
            rest = re.sub(r"^(?:sold\s+to|client|buyer|customer|odbiorca|nabywca)\s*[:\s]*", "", line, flags=re.I).strip()
            if rest and len(rest) > 2:
                client = rest
            elif i + 1 < len(lines) and len(lines[i + 1]) > 2:
                client = lines[i + 1]
            break
    # Seller: often first non-numeric, non-date line (company name)
    for line in lines[:15]:
        if len(line) < 4:
            continue
        if re.match(r"^[\d\s.,\-/]+$", line):
            continue
        if re.search(r"invoice|date|vat|tax|net|gross", line, re.I):
            continue
        if not seller:
            seller = line
            break
    return seller, client


def extract_structured(text: str) -> dict:
    """Apply deterministic regex rules to OCR text; return dict with REQUIRED_FIELDS."""
    result = {f: None for f in REQUIRED_FIELDS}
    text_nl = text.replace("\r", "\n")

    seller_name, client_name = _extract_names_from_text(text_nl)
    result["seller_name"] = seller_name
    result["client_name"] = client_name

    result["seller_tax_id"] = _first_match(text_nl, PATTERNS["seller_tax_id"])
    result["client_tax_id"] = _first_match(text_nl, PATTERNS["client_tax_id"])
    result["invoice_number"] = _first_match(text_nl, PATTERNS["invoice_number"])
    result["invoice_date"] = _first_match(text_nl, PATTERNS["invoice_date"])

    net_s = _first_match(text_nl, PATTERNS["net_worth"])
    vat_s = _first_match(text_nl, PATTERNS["vat"])
    gross_s = _first_match(text_nl, PATTERNS["gross_worth"])
    result["net_worth"] = _parse_number(net_s)
    result["vat"] = _parse_number(vat_s)
    result["gross_worth"] = _parse_number(gross_s)

    return result


def extract_invoice_pipeline_b(image_path: Path) -> Optional[dict]:
    """
    Full Pipeline B: OCR -> regex extraction -> structured dict.
    No LLM. Returns None on critical failure.
    """
    try:
        text = run_ocr(image_path)
        if not text.strip():
            logger.warning("No text from OCR for %s (Pipeline B)", image_path)
            return {f: None for f in REQUIRED_FIELDS}
        return extract_structured(text)
    except Exception as e:
        logger.exception("Pipeline B failed for %s: %s", image_path, e)
        return None
