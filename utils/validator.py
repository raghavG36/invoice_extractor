"""
Validation engine: compare pipeline A vs pipeline B outputs field-by-field.
"""
import logging
from typing import Any, List

from invoice_extractor.config import REQUIRED_FIELDS, FLOAT_TOLERANCE

logger = logging.getLogger(__name__)


def _values_match(field_name: str, a: Any, b: Any) -> bool:
    """Compare two normalized values with type-aware logic."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if field_name in ("net_worth", "vat", "gross_worth"):
        try:
            fa, fb = float(a), float(b)
            return abs(fa - fb) <= FLOAT_TOLERANCE
        except (TypeError, ValueError):
            return str(a).strip() == str(b).strip()
    # Strings, dates
    return str(a).strip().lower() == str(b).strip().lower()


def compare_invoices(
    file_name: str,
    pipeline_a_output: dict,
    pipeline_b_output: dict,
) -> List[dict]:
    """
    Compare pipeline A and B outputs field-by-field.
    Returns list of rows: file_name, field_name, pipeline_a_value, pipeline_b_value, match.
    """
    rows = []
    for field_name in REQUIRED_FIELDS:
        va = pipeline_a_output.get(field_name)
        vb = pipeline_b_output.get(field_name)
        match = _values_match(field_name, va, vb)
        rows.append({
            "file_name": file_name,
            "field_name": field_name,
            "pipeline_a_value": va if va is None else str(va),
            "pipeline_b_value": vb if vb is None else str(vb),
            "match": match,
        })
        if not match:
            logger.debug(
                "Mismatch %s: A=%r B=%r",
                field_name, va, vb,
                extra={"file": file_name},
            )
    return rows


def reconcile_value(
    field_name: str,
    pipeline_a_value: Any,
    pipeline_b_value: Any,
    prefer_b_on_mismatch: bool = True,
) -> Any:
    """Pick final value: if match use either; if mismatch prefer B when prefer_b_on_mismatch."""
    if _values_match(field_name, pipeline_a_value, pipeline_b_value):
        return pipeline_b_value if pipeline_b_value is not None else pipeline_a_value
    if prefer_b_on_mismatch:
        return pipeline_b_value
    return pipeline_a_value


def build_reconciled_invoice(
    file_name: str,
    pipeline_a_output: dict,
    pipeline_b_output: dict,
) -> dict:
    """Build final reconciled record (prefer Pipeline B on mismatch)."""
    row = {"file_name": file_name}
    for field_name in REQUIRED_FIELDS:
        va = pipeline_a_output.get(field_name)
        vb = pipeline_b_output.get(field_name)
        row[field_name] = reconcile_value(field_name, va, vb, prefer_b_on_mismatch=True)
    return row
