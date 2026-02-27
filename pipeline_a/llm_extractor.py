"""
Pipeline A: OCR (pytesseract only) + LLM extraction (OpenAI, Gemini, or Ollama).
Returns structured dict with required fields only; strict JSON, no markdown.
"""
import json
import logging
import re
from pathlib import Path
from typing import Optional

from invoice_extractor.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    TESSERACT_CMD,
    REQUIRED_FIELDS,
)
# Azure OCR (commented out for now; using Tesseract only)
# from invoice_extractor.config import OCR_BACKEND, AZURE_VISION_KEY, AZURE_VISION_ENDPOINT
from invoice_extractor.models import InvoiceData

logger = logging.getLogger(__name__)

# Optional imports with fallback
try:
    import pytesseract
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

_OPENAI_AVAILABLE = False
try:
    from openai import OpenAI
    _OPENAI_AVAILABLE = True
except ImportError:
    pass

_GEMINI_AVAILABLE = False
try:
    import google.generativeai as genai
    _GEMINI_AVAILABLE = True
except ImportError:
    pass


EXTRACTION_PROMPT = """You are an invoice data extractor. Extract the following fields from the invoice text below. Return ONLY valid JSON with exactly these keys (use null for missing values). No explanation, no markdown, no code block.

Required keys:
- seller_name (string)
- seller_tax_id (string)
- client_name (string)
- client_tax_id (string)
- invoice_number (string)
- invoice_date (string, any format)
- net_worth (number)
- vat (number)
- gross_worth (number)

Invoice text:
---
{text}
---

Return only the JSON object, nothing else."""


def _repair_json(s: str) -> str:
    """Try to fix common LLM JSON mistakes (trailing commas, missing closing braces)."""
    s = s.strip()
    # Remove trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)
    # Close truncated object/array (e.g. Ollama omits final })
    open_braces = s.count("{") - s.count("}")
    open_brackets = s.count("[") - s.count("]")
    if open_braces > 0 or open_brackets > 0:
        s = s + "]" * open_brackets + "}" * open_braces
    return s


def _parse_llm_json(content: str) -> dict:
    """Parse JSON from LLM, with optional repair for common mistakes."""
    content = content.strip()
    # Strip markdown code block if present
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    # Try repaired (trailing commas, etc.)
    repaired = _repair_json(content)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        raise


def ocr_with_pytesseract(image_path: Path) -> str:
    """Extract raw text using pytesseract."""
    if not _PIL_AVAILABLE:
        raise RuntimeError("PIL and pytesseract are required for OCR. Install: pip install Pillow pytesseract")
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    try:
        img = Image.open(image_path)
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
        return text or ""
    except Exception as e:
        logger.exception("Pytesseract OCR failed for %s: %s", image_path, e)
        raise


# --- Azure OCR (commented out; using Tesseract only for now) ---
# def ocr_with_azure(image_path: Path) -> str:
#     """Extract raw text using Azure Computer Vision OCR."""
#     if not AZURE_VISION_KEY or not AZURE_VISION_ENDPOINT:
#         raise RuntimeError("AZURE_VISION_KEY and AZURE_VISION_ENDPOINT must be set for Azure OCR")
#     try:
#         from azure.ai.vision.imageanalysis import ImageAnalysisClient
#         from azure.ai.vision.imageanalysis.models import VisualFeatures
#         from azure.core.credentials import AzureKeyCredential
#
#         client = ImageAnalysisClient(
#             endpoint=AZURE_VISION_ENDPOINT,
#             credential=AzureKeyCredential(AZURE_VISION_KEY),
#         )
#         with open(image_path, "rb") as f:
#             result = client.analyze(image_data=f.read(), visual_features=[VisualFeatures.READ])
#         if result.read and result.read.blocks:
#             return " ".join(
#                 line.content
#                 for block in result.read.blocks
#                 for line in (block.lines or [])
#             )
#         return ""
#     except ImportError:
#         raise RuntimeError(
#             "Azure Vision package not installed. pip install azure-ai-vision-imageanalysis"
#         )
#     except Exception as e:
#         logger.exception("Azure OCR failed for %s: %s", image_path, e)
#         raise


def run_ocr(image_path: Path) -> str:
    """Run OCR using Tesseract (pytesseract) only."""
    return ocr_with_pytesseract(image_path)


def _get_llm_client():
    """Return OpenAI or OpenAI-compatible (Ollama) client. Not used for Gemini."""
    if not _OPENAI_AVAILABLE:
        raise RuntimeError("OpenAI package required. pip install openai")
    if LLM_PROVIDER == "ollama":
        return OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY must be set for OpenAI (or set INVOICE_LLM_PROVIDER=ollama for local)"
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def _extract_with_gemini(prompt: str) -> dict:
    """Call Gemini API and return parsed invoice dict."""
    if not _GEMINI_AVAILABLE:
        raise RuntimeError("Gemini package required. pip install google-generativeai")
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY must be set for Gemini. Get one at https://aistudio.google.com/apikey"
        )
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0),
    )
    content = (response.text or "").strip()
    logger.info("LLM response: %s", content)
    data = _parse_llm_json(content)
    return InvoiceData.from_dict(data).to_dict()


def extract_with_llm(raw_text: str) -> dict:
    """Send text to LLM (OpenAI, Gemini, or Ollama) and parse strict JSON. Returns dict with required fields only."""
    prompt = EXTRACTION_PROMPT.format(text=raw_text[:12000])  # token limit safety

    if LLM_PROVIDER == "gemini":
        try:
            return _extract_with_gemini(prompt)
        except json.JSONDecodeError as e:
            logger.warning("LLM returned invalid JSON: %s", e)
            return {f: None for f in REQUIRED_FIELDS}
        except Exception as e:
            logger.exception("LLM extraction failed: %s", e)
            raise

    client = _get_llm_client()
    model = OPENAI_MODEL if LLM_PROVIDER == "openai" else OLLAMA_MODEL
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        logger.info("LLM response: %s", content)
        data = _parse_llm_json(content)
        return InvoiceData.from_dict(data).to_dict()
    except json.JSONDecodeError as e:
        logger.warning("LLM returned invalid JSON: %s. Raw response: %s", e, content)
        return {f: None for f in REQUIRED_FIELDS}
    except Exception as e:
        logger.exception("LLM extraction failed: %s", e)
        raise


def extract_invoice_pipeline_a(image_path: Path) -> Optional[dict]:
    """
    Full Pipeline A: OCR -> LLM -> structured dict.
    Returns None on failure (caller can skip/log).
    """
    try:
        text = run_ocr(image_path)
        if not text.strip():
            logger.warning("No text from OCR for %s", image_path)
            return {f: None for f in REQUIRED_FIELDS}
        return extract_with_llm(text)
    except Exception as e:
        logger.exception("Pipeline A failed for %s: %s", image_path, e)
        return None
