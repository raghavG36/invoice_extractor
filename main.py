"""
Main entry point: load images, run Pipeline A and B, normalize, compare, write CSVs, print metrics.
Run from repo root: python invoice_extractor/main.py
Or: python -m invoice_extractor.main
"""
import csv
import logging
import sys
from pathlib import Path

# Ensure package root is on path when run as script
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from invoice_extractor.config import (
    IMAGES_DIR,
    IMAGE_PREFIX,
    IMAGE_START,
    IMAGE_END,
    IMAGE_EXT,
    OUTPUTS_DIR,
    REQUIRED_FIELDS,
)
from invoice_extractor.pipeline_a.llm_extractor import extract_invoice_pipeline_a
from invoice_extractor.pipeline_b.structured_extractor import extract_invoice_pipeline_b
from invoice_extractor.utils.normalizer import normalize_invoice_dict
from invoice_extractor.utils.validator import (
    compare_invoices,
    build_reconciled_invoice,
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def get_image_paths() -> list[Path]:
    """Return list of image paths (batch1-0331 to batch1-0381)."""
    paths = []
    for i in range(IMAGE_START, IMAGE_END + 1):
        name = f"{IMAGE_PREFIX}{i:04d}.{IMAGE_EXT}"
        p = IMAGES_DIR / name
        if p.exists():
            paths.append(p)
        else:
            logger.warning("Image not found: %s", p)
    return paths


def _safe_run_pipeline(extract_fn, path: Path, pipeline_name: str) -> dict | None:
    """Run extractor; on exception return None and log."""
    try:
        return extract_fn(path)
    except Exception as e:
        logger.exception("%s failed for %s: %s", pipeline_name, path.name, e)
        return None


def main() -> None:
    logger.info("Starting invoice extraction (Pipeline A + B)")
    image_paths = get_image_paths()
    if not image_paths:
        logger.error("No images found in %s (prefix=%s, range=%s-%s)",
                     IMAGES_DIR, IMAGE_PREFIX, IMAGE_START, IMAGE_END)
        sys.exit(1)
    logger.info("Found %d images", len(image_paths))

    output_rows = []
    comparison_rows = []
    total_fields = 0
    matched_fields = 0
    docs_processed = 0
    docs_full_match = 0

    for path in image_paths:
        file_name = path.name
        logger.info("Processing %s", file_name)

        a_raw = _safe_run_pipeline(extract_invoice_pipeline_a, path, "Pipeline A")
        b_raw = _safe_run_pipeline(extract_invoice_pipeline_b, path, "Pipeline B")

        if a_raw is None:
            a_raw = {f: None for f in REQUIRED_FIELDS}
        if b_raw is None:
            b_raw = {f: None for f in REQUIRED_FIELDS}

        a_norm = normalize_invoice_dict(a_raw)
        b_norm = normalize_invoice_dict(b_raw)

        comp = compare_invoices(file_name, a_norm, b_norm)
        comparison_rows.extend(comp)

        reconciled = build_reconciled_invoice(file_name, a_norm, b_norm)
        output_rows.append(reconciled)

        # Metrics
        doc_matches = sum(1 for r in comp if r["match"])
        total_fields += len(REQUIRED_FIELDS)
        matched_fields += doc_matches
        docs_processed += 1
        if doc_matches == len(REQUIRED_FIELDS):
            docs_full_match += 1
        if doc_matches < len(REQUIRED_FIELDS):
            for r in comp:
                if not r["match"]:
                    logger.info("Mismatch %s | %s: A=%r B=%r",
                                file_name, r["field_name"],
                                r["pipeline_a_value"], r["pipeline_b_value"])

    # Write output.csv
    output_csv = OUTPUTS_DIR / "output.csv"
    out_cols = ["file_name"] + REQUIRED_FIELDS
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(output_rows)
    logger.info("Wrote %s", output_csv)

    # Write comparison_report.csv
    report_csv = OUTPUTS_DIR / "comparison_report.csv"
    report_cols = ["file_name", "field_name", "pipeline_a_value", "pipeline_b_value", "match"]
    with open(report_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=report_cols)
        w.writeheader()
        w.writerows(comparison_rows)
    logger.info("Wrote %s", report_csv)

    # Summary metrics
    field_accuracy = (matched_fields / total_fields * 100) if total_fields else 0
    doc_accuracy = (docs_full_match / docs_processed * 100) if docs_processed else 0
    print("\n--- Summary metrics ---")
    print(f"Images processed:     {docs_processed}")
    print(f"Field Accuracy:       {field_accuracy:.1f}%")
    print(f"Document Accuracy:    {doc_accuracy:.1f}%")
    print(f"Total field matches:  {matched_fields} / {total_fields}")
    print(f"Documents full match: {docs_full_match} / {docs_processed}")
    print("-----------------------\n")


if __name__ == "__main__":
    main()
