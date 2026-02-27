# Invoice Extraction

Extract structured invoice data from image invoices using two pipelines: **Pipeline A** (OCR + LLM) and **Pipeline B** (OCR + regex). Results are normalized, compared, and written to CSV.

## Overview

- **Pipeline A:** Runs OCR (Tesseract; Azure optional) on each invoice image, then sends the text to an LLM (OpenAI, Gemini, or local Ollama) to extract structured fields.
- **Pipeline B:** Runs the same OCR, then uses regex and heuristics to extract the same fields without an LLM.
- **Flow:** For each image, both pipelines run → outputs are normalized (dates, numbers) → results are compared field-by-field → a **reconciled** row (preferring Pipeline B on mismatch) is written to `output.csv`, and the A vs B comparison is written to `comparison_report.csv`. A short accuracy summary is printed at the end.

This setup lets you compare LLM-based extraction against rule-based extraction and tune or trust one pipeline over the other.

## Current approach (how we get to the solution)

1. **Single OCR for both pipelines**  
   Tesseract (pytesseract) runs once per image. Pipeline B reuses the same `run_ocr()` from Pipeline A, so there is no duplicate OCR and both pipelines see the same raw text.

2. **Pipeline A — OCR + LLM**  
   - OCR text is sent to an LLM (OpenAI, Gemini, or Ollama) with a **strict JSON extraction prompt** (required keys only; no markdown).  
   - The model is asked to return only a JSON object. Responses are **repaired** when needed (trailing commas, missing `}`, markdown code fences stripped) before parsing.  
   - Parsed data is validated and mapped to the fixed field set via `InvoiceData`; only the required fields are returned.

3. **Pipeline B — OCR + regex and heuristics**  
   - The same OCR text is processed with **deterministic regex patterns** for labels like `Seller:`, `Client:`, `Tax Id`, `Invoice no`, `Net worth`, `VAT`, `Gross worth`.  
   - For seller/client names, if label-based patterns miss, a **heuristic** is used (e.g. “Sold to” / “Client” for buyer; first plausible company-like line for seller).  
   - Numeric fields are parsed from captured strings (commas/dots normalized to float). No LLM.

4. **Normalization**  
   Both pipelines’ outputs are **normalized** before comparison: dates → ISO `YYYY-MM-DD`, currency → float, tax IDs → spaces removed, names → lowercase and trimmed. This makes A vs B comparison consistent.

5. **Comparison and reconciliation**  
   - **Comparison:** Field-by-field with type-aware rules (floats compared within `INVOICE_FLOAT_TOLERANCE`; strings/dates case-insensitive).  
   - **Reconciliation:** For each field, if A and B match we keep that value; if they differ, we **prefer Pipeline B** (`prefer_b_on_mismatch=True`). The reconciled row is what goes into `output.csv`.

6. **Outputs and metrics**  
   - `output.csv`: one row per image with `file_name` and the reconciled extracted fields.  
   - `comparison_report.csv`: every field for every image with A value, B value, and match flag.  
   - Console: summary counts (images processed, field accuracy %, document accuracy %, total matches).

## Requirements

- **Python 3.10+**
- **Tesseract OCR** (for default OCR). Install separately:
  - **Windows:** [Tesseract at UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) — run the installer and optionally add to PATH.
  - **macOS:** `brew install tesseract`
  - **Linux:** `sudo apt install tesseract-ocr` (or equivalent)
- **LLM for Pipeline A:** either an **OpenAI API key** or local **Ollama** (no key needed)

## Installation

1. Clone or open the project, then create and activate a virtual environment:

   ```bash
   cd invoice-extraction
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

2. Install dependencies (from repo root or from `invoice_extractor/`):

   ```bash
   pip install -r invoice_extractor/requirements.txt
   ```

3. Copy `invoice_extractor/.env.example` to `.env` (in repo root or in `invoice_extractor/`) and set:

   - For **OpenAI:** `OPENAI_API_KEY` and `INVOICE_LLM_PROVIDER=openai`.
   - For **Gemini (free, good for Colab):** `GEMINI_API_KEY` and `INVOICE_LLM_PROVIDER=gemini` (get key at [Google AI Studio](https://aistudio.google.com/apikey)).
   - For **Ollama (local):** `INVOICE_LLM_PROVIDER=ollama` (default); ensure Ollama is running and a model is pulled (e.g. `ollama pull llama3.2`).
   - `TESSERACT_CMD` — (Windows, optional) full path to `tesseract.exe` if Tesseract is not in PATH.

## Configuration

Environment variables (in `.env` or the shell):

| Variable | Description |
|----------|-------------|
| `INVOICE_LLM_PROVIDER` | `ollama` (default), `openai`, or `gemini` |
| `OPENAI_API_KEY` | OpenAI API key (required when provider is `openai`) |
| `OPENAI_INVOICE_MODEL` | OpenAI model (default: `gpt-4o-mini`) |
| `GEMINI_API_KEY` | Gemini API key (required when provider is `gemini`; get at [AI Studio](https://aistudio.google.com/apikey)) |
| `GEMINI_INVOICE_MODEL` | Gemini model (default: `gemini-1.5-flash`) |
| `OLLAMA_BASE_URL` | Ollama API URL (default: `http://localhost:11434/v1`) |
| `OLLAMA_MODEL` | Ollama model name (default: `llama3`) |
| `TESSERACT_CMD` | Path to Tesseract executable (optional; use if not in PATH) |
| `INVOICE_IMAGES_DIR` | Directory containing invoice images (default: `invoice_extractor/images/`) |
| `INVOICE_IMAGE_PREFIX` | Filename prefix (default: `batch1-`) |
| `INVOICE_IMAGE_START` | Start index for image range (default: `348`) |
| `INVOICE_IMAGE_END` | End index for image range (default: `350`) |
| `INVOICE_IMAGE_EXT` | Image extension (default: `jpg`) |
| `INVOICE_FLOAT_TOLERANCE` | Tolerance for numeric comparison (default: `0.01`) |
| `INVOICE_OCR_BACKEND` | `pytesseract` (default) or `azure` (optional; see Azure OCR section) |
| `AZURE_VISION_KEY`, `AZURE_VISION_ENDPOINT` | For Azure Computer Vision OCR when `INVOICE_OCR_BACKEND=azure` |

## Usage

From the project root:

```bash
python main.py
```

Or run the package entry point:

```bash
python -m invoice_extractor.main
```

Place invoice images in the configured directory (default: `invoice_extractor/images/`; you can use a subfolder such as `batch_1/batch_1/batch1_1/`) with names like `batch1-0348.jpg`, `batch1-0349.jpg`, etc. The default range is indices 348–350 (three images). Adjust `INVOICE_IMAGE_PREFIX`, `INVOICE_IMAGE_START`, `INVOICE_IMAGE_END`, and `INVOICE_IMAGE_EXT` to match your naming and range.

## Outputs

- **`invoice_extractor/outputs/output.csv`** — Reconciled invoice data (one row per image: `file_name` + extracted fields).
- **`invoice_extractor/outputs/comparison_report.csv`** — Field-by-field comparison of Pipeline A vs B (`file_name`, `field_name`, `pipeline_a_value`, `pipeline_b_value`, `match`).

A short summary is printed: images processed, field accuracy, document accuracy, and match counts.

## Extracted Fields

- `seller_name`, `seller_tax_id`
- `client_name`, `client_tax_id`
- `invoice_number`, `invoice_date`
- `net_worth`, `vat`, `gross_worth`

## Project Structure

```
invoice-extraction/
├── main.py                 # Entry point from repo root: python main.py
├── .env.example            # Optional at root; copy to .env
├── invoice_extractor/
│   ├── README.md           # This file
│   ├── config.py           # Env-based configuration
│   ├── main.py             # Core loop: load images, run A+B, compare, write CSVs
│   ├── models.py           # Invoice data models
│   ├── requirements.txt    # pip install -r invoice_extractor/requirements.txt
│   ├── .env.example        # Copy to invoice_extractor/.env or repo root .env
│   ├── pipeline_a/         # OCR (Tesseract/Azure) + LLM extraction
│   ├── pipeline_b/         # OCR + regex-based extraction
│   ├── utils/              # Normalizer, validator
│   ├── images/             # Default image directory (or set INVOICE_IMAGES_DIR)
│   ├── outputs/            # output.csv, comparison_report.csv
│   └── colab_setup.ipynb   # Colab notebook to run in Google Colab
└── colab_setup.ipynb       # Alternative Colab entry at repo root
```

## Optional: Local Ollama

To use a local LLM (no OpenAI API key) for Pipeline A:

1. Install and start [Ollama](https://ollama.com), then pull a model: e.g. `ollama pull llama3` or `ollama pull llama3.2`
2. In `.env` set: `INVOICE_LLM_PROVIDER=ollama`. Optionally set `OLLAMA_MODEL` (default `llama3`) and `OLLAMA_BASE_URL` (default `http://localhost:11434/v1`).

Pipeline A will then call your local Ollama instance for extraction.

## Optional: Azure OCR

To use Azure Computer Vision instead of Tesseract for Pipeline A:

1. Add `azure-ai-vision-imageanalysis>=1.0.0b1` to `invoice_extractor/requirements.txt` and install.
2. Uncomment the Azure-related variables in `invoice_extractor/config.py` if they are commented out.
3. Set in `.env`: `INVOICE_OCR_BACKEND=azure`, `AZURE_VISION_KEY`, `AZURE_VISION_ENDPOINT`.

Pipeline B uses the same OCR layer (Tesseract or Azure, depending on config).

## Google Colab

You can run the pipeline in [Google Colab](https://colab.research.google.com) (no local Ollama; use **Gemini** or OpenAI).

1. Open **`invoice_extractor/colab_setup.ipynb`** or **`colab_setup.ipynb`** at repo root in Colab (upload the repo or open from GitHub).
2. In the first code cell, replace the clone URL with your repo if needed (or upload the project and skip the clone / `%cd` into the uploaded folder).
3. Run the install cell: it installs Tesseract and `pip install -r invoice_extractor/requirements.txt` (or `-r requirements.txt` if the notebook’s working directory is already `invoice_extractor/`).
4. **Gemini (free):** Set `INVOICE_LLM_PROVIDER=gemini` and your **`GEMINI_API_KEY`** (get one at [Google AI Studio](https://aistudio.google.com/apikey); or add as Colab **Secrets**).  
   **OpenAI:** Set `INVOICE_LLM_PROVIDER=openai` and your `OPENAI_API_KEY`.
5. Run the pipeline with `python -m invoice_extractor.main`.

Optionally mount Google Drive and set `INVOICE_IMAGES_DIR` to a folder on Drive containing your invoice images.
