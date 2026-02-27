"""
Normalization layer for invoice field values before comparison.
Currency → float, dates → ISO, tax IDs → no spaces, names → lowercase + strip.
"""
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def normalize_currency(value: Any) -> Optional[float]:
    """Convert currency string to float. Remove commas, symbols; handle empty."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if value == value else None  # NaN check
    s = str(value).strip()
    if not s or s.lower() in ("", "n/a", "nan", "null", "-"):
        return None
    # Remove currency symbols, spaces, commas; keep digits, minus, dot
    cleaned = re.sub(r"[^\d.\-]", "", s.replace(",", "."))
    # Handle multiple dots (take last as decimal)
    parts = cleaned.split(".")
    if len(parts) > 2:
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Could not parse currency: %r", value)
        return None


def normalize_date(value: Any) -> Optional[str]:
    """Normalize date to ISO format YYYY-MM-DD. Accepts various formats."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("", "n/a", "nan", "null"):
        return None
    # Already ISO-like
    iso_match = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if iso_match:
        y, m, d = iso_match.groups()
        if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{m}-{d}"
    # DD.MM.YYYY or DD/MM/YYYY
    for sep in [".", "/", "-"]:
        parts = re.split(r"[\s./\-]+", s)
        if len(parts) >= 3:
            try:
                if len(parts[0]) == 4 and len(parts[-1]) in (2, 4):  # YYYY MM DD
                    y, m, d = parts[0], parts[1], parts[2]
                else:
                    d, m, y = parts[0], parts[1], parts[2]
                y = int(y)
                if y < 100:
                    y += 2000 if y < 50 else 1900
                m = int(m)
                d = int(d)
                if 1 <= m <= 12 and 1 <= d <= 31:
                    return f"{y:04d}-{m:02d}-{d:02d}"
            except (ValueError, IndexError):
                continue
    logger.warning("Could not parse date: %r", value)
    return None


def normalize_tax_id(value: Any) -> Optional[str]:
    """Remove spaces from tax ID."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return re.sub(r"\s+", "", s)


def normalize_name(value: Any) -> Optional[str]:
    """Lowercase and strip whitespace for names."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return " ".join(s.lower().split())


def normalize_string(value: Any) -> Optional[str]:
    """Generic string: strip and collapse whitespace; empty → None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return " ".join(s.split())


# Field-to-normalizer mapping
CURRENCY_FIELDS = {"net_worth", "vat", "gross_worth"}
DATE_FIELDS = {"invoice_date"}
TAX_ID_FIELDS = {"seller_tax_id", "client_tax_id"}
NAME_FIELDS = {"seller_name", "client_name"}
STRING_FIELDS = {"invoice_number"}


def normalize_field(field_name: str, value: Any) -> Any:
    """Normalize a single field by name."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if field_name in CURRENCY_FIELDS:
        return normalize_currency(value)
    if field_name in DATE_FIELDS:
        return normalize_date(value)
    if field_name in TAX_ID_FIELDS:
        return normalize_tax_id(value)
    if field_name in NAME_FIELDS:
        return normalize_name(value)
    if field_name in STRING_FIELDS:
        return normalize_string(value)
    return normalize_string(value)


def normalize_invoice_dict(data: dict) -> dict:
    """Normalize a full invoice dict (all required fields)."""
    from invoice_extractor.config import REQUIRED_FIELDS

    result = {}
    for key in REQUIRED_FIELDS:
        result[key] = normalize_field(key, data.get(key))
    return result
