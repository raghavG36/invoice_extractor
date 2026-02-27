"""
Configuration for invoice extraction system.
Uses environment variables for API keys and paths.
"""
import os
from pathlib import Path

# Base paths (needed before load_dotenv so we can load .env from package dir)
PROJECT_ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    # Load .env from package directory so it works when run from repo root
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass
IMAGES_BASE = PROJECT_ROOT / "images"
# Default: batch_1/batch_1/batch1_1/ with batch1-0331.jpg to batch1-0381.jpg
IMAGES_DIR = Path(os.getenv("INVOICE_IMAGES_DIR", str(IMAGES_BASE)))
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Image range (batch1-0331 to batch1-0381 = 50 images)
IMAGE_PREFIX = os.getenv("INVOICE_IMAGE_PREFIX", "batch1-")
IMAGE_START = int(os.getenv("INVOICE_IMAGE_START", "348"))
IMAGE_END = int(os.getenv("INVOICE_IMAGE_END", "350"))
IMAGE_EXT = os.getenv("INVOICE_IMAGE_EXT", "jpg")

# Pipeline A: OCR + LLM — "openai", "gemini" (free in Colab), or "ollama" (local)
LLM_PROVIDER = os.getenv("INVOICE_LLM_PROVIDER", "ollama").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_INVOICE_MODEL", "gpt-4o-mini")
# Gemini (free tier; good for Colab): API key from https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_INVOICE_MODEL", "gemini-1.5-flash")
# Ollama (local): base URL and model name. Must match a model you have (ollama list / ollama pull <name>).
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
if not OLLAMA_BASE_URL.rstrip("/").endswith("/v1"):
    OLLAMA_BASE_URL = OLLAMA_BASE_URL.rstrip("/") + "/v1"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")  # e.g. llama3, llama3.2, mistral
# OCR: Tesseract only. Azure commented out for now.
# OCR_BACKEND = os.getenv("INVOICE_OCR_BACKEND", "pytesseract")
# Path to tesseract executable (optional; required on Windows if tesseract is not in PATH)
_tesseract_env = os.getenv("TESSERACT_CMD", "").strip() or None
if _tesseract_env is None and os.name == "nt":
    _default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.isfile(_default_tesseract):
        _tesseract_env = _default_tesseract
TESSERACT_CMD = _tesseract_env
# Azure OCR (commented out; using Tesseract only)
# AZURE_VISION_KEY = os.getenv("AZURE_VISION_KEY", "")
# AZURE_VISION_ENDPOINT = os.getenv("AZURE_VISION_ENDPOINT", "")

# Pipeline B: deterministic (regex) - no extra config

# Required fields for extraction and output
REQUIRED_FIELDS = [
    "seller_name",
    "seller_tax_id",
    "client_name",
    "client_tax_id",
    "invoice_number",
    "invoice_date",
    "net_worth",
    "vat",
    "gross_worth",
]

# Float comparison tolerance
FLOAT_TOLERANCE = float(os.getenv("INVOICE_FLOAT_TOLERANCE", "0.01"))

# Ensure outputs directory exists
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
