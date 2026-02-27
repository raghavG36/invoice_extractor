# Invoice Extraction — Learning Guide

This guide helps you **onboard** to the project and **make changes** safely. Use it when you’re new to the repo or when you need to add fields, tweak extraction, or change reconciliation behavior.

---

## 1. Onboarding

### 1.1 What the project does

- **Input:** Invoice images (e.g. `batch1-0348.jpg`, `batch1-0349.jpg`).
- **Two pipelines:**
  - **Pipeline A:** OCR (Tesseract) → LLM (Ollama or OpenAI) → structured JSON.
  - **Pipeline B:** Same OCR → regex/heuristics → same structured fields.
- **Output:**  
  - Reconciled rows in `output.csv` (one row per image).  
  - Field-by-field A vs B comparison in `comparison_report.csv`.  
  - Summary metrics (field accuracy, document accuracy) printed at the end.

Reconciliation prefers **Pipeline B** when A and B disagree (configurable in code).

### 1.2 Get running in 5 steps

1. **Clone and enter the project**
   ```bash
   cd invoice-extraction
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Tesseract** (if not already):
   - **Windows:** [Tesseract at UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) — install and optionally add to PATH.
   - **macOS:** `brew install tesseract`
   - **Linux:** `sudo apt install tesseract-ocr`

5. **Configure environment**
   - Copy `.env.example` to `.env` (in `invoice_extractor/` or project root).
   - For **Ollama (local):** `INVOICE_LLM_PROVIDER=ollama`; ensure Ollama is running and a model is pulled (e.g. `ollama pull llama3`).
   - For **OpenAI:** set `INVOICE_LLM_PROVIDER=openai` and `OPENAI_API_KEY`.
   - On Windows, set `TESSERACT_CMD` to the path of `tesseract.exe` if it’s not in PATH.

6. **Place images** in the configured folder (default: `invoice_extractor/images/...`) with names like `batch1-0348.jpg`. Adjust `INVOICE_IMAGE_PREFIX`, `INVOICE_IMAGE_START`, `INVOICE_IMAGE_END`, `INVOICE_IMAGE_EXT` in `.env` to match.

7. **Run**
   ```bash
   python main.py
   ```
   Or: `python -m invoice_extractor.main`

Outputs appear in `invoice_extractor/outputs/`: `output.csv` and `comparison_report.csv`.

---

## 2. Project structure and data flow

### 2.1 Key files (what to touch when)

| File / folder | Purpose |
|---------------|--------|
| `main.py` (root) | Thin entry point; calls `invoice_extractor.main`. |
| `invoice_extractor/main.py` | Core loop: discover images → run A + B → normalize → compare → reconcile → write CSVs + summary. |
| `invoice_extractor/config.py` | All env-based config: paths, image range, LLM/OCR settings, **REQUIRED_FIELDS**. |
| `invoice_extractor/models.py` | Pydantic `InvoiceData` — schema for extracted fields. |
| `invoice_extractor/pipeline_a/llm_extractor.py` | OCR + LLM extraction; prompt and JSON parsing. |
| `invoice_extractor/pipeline_b/structured_extractor.py` | OCR + regex patterns and name heuristics. |
| `invoice_extractor/utils/normalizer.py` | Normalize field values (dates → ISO, numbers → float, etc.) before comparison. |
| `invoice_extractor/utils/validator.py` | Compare A vs B and build reconciled row. |

### 2.2 Data flow (one image)

```
Image path
    → Pipeline A: OCR → LLM → dict (REQUIRED_FIELDS)
    → Pipeline B: OCR → regex → dict (REQUIRED_FIELDS)
    → normalize_invoice_dict() on both
    → compare_invoices() → rows for comparison_report.csv
    → build_reconciled_invoice() → one row for output.csv
```

Everything is driven by **REQUIRED_FIELDS** in `config.py`. Adding or removing a field means updating that list and all places that depend on it (see below).

---

## 3. Making changes

### 3.1 Changing configuration (paths, range, LLM, OCR)

**Where:** `invoice_extractor/config.py` and `.env`.

- **Image directory and range:** `IMAGES_DIR`, `IMAGE_PREFIX`, `IMAGE_START`, `IMAGE_END`, `IMAGE_EXT`. Prefer setting via env: `INVOICE_IMAGES_DIR`, `INVOICE_IMAGE_PREFIX`, etc.
- **LLM:** `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.
- **Tesseract:** `TESSERACT_CMD` (optional; default Windows path is in `config.py`).
- **Float comparison:** `FLOAT_TOLERANCE` for comparing `net_worth`, `vat`, `gross_worth`.

No need to touch pipelines or models for these.

---

### 3.2 Adding a new extracted field

You need to add the field in **five** places so that both pipelines extract it, it’s normalized, compared, and written to CSV.

1. **`invoice_extractor/config.py`**  
   Append the new key to `REQUIRED_FIELDS`:
   ```python
   REQUIRED_FIELDS = [
       "seller_name",
       # ... existing ...
       "gross_worth",
       "your_new_field",  # e.g. "currency", "payment_due_date"
   ]
   ```

2. **`invoice_extractor/models.py`**  
   Add the attribute to `InvoiceData` and to `to_dict()` / `from_dict()`:
   ```python
   class InvoiceData(BaseModel):
       # ... existing ...
       your_new_field: Optional[str] = None  # or float, etc.

       def to_dict(self) -> dict:
           return {
               # ... existing ...
               "your_new_field": self.your_new_field,
           }

       @classmethod
       def from_dict(cls, data: dict) -> "InvoiceData":
           allowed = {
               # ... existing keys ...
               "your_new_field",
           }
   ```

3. **Pipeline A — `invoice_extractor/pipeline_a/llm_extractor.py`**  
   - Add the field to `EXTRACTION_PROMPT` (required keys and types), e.g.:
     - `your_new_field (string)`
   - The LLM response is already parsed into a dict and passed through `InvoiceData.from_dict(data).to_dict()`, so as long as the key is in `REQUIRED_FIELDS` and in the model, it will be included.

4. **Pipeline B — `invoice_extractor/pipeline_b/structured_extractor.py`**  
   - In `PATTERNS`, add a list of regex patterns for the new field (if it’s pattern-based).
   - In `extract_structured()`, set `result["your_new_field"]` from `_first_match(text_nl, PATTERNS["your_new_field"])` or from a small helper (e.g. like `_extract_names_from_text` for names).
   - If it’s a number, use a `_parse_number`-style helper and assign the parsed value.

5. **`invoice_extractor/utils/normalizer.py`**  
   - Decide how the field should be normalized (string, date, number, tax_id, etc.).
   - Add it to the right set: `CURRENCY_FIELDS`, `DATE_FIELDS`, `TAX_ID_FIELDS`, `NAME_FIELDS`, or `STRING_FIELDS`.  
   - If it’s a new “kind” (e.g. a special string format), add a normalizer and a branch in `normalize_field()`.

6. **`invoice_extractor/utils/validator.py`**  
   - No change needed: `compare_invoices` and `build_reconciled_invoice` iterate over `REQUIRED_FIELDS`, so the new field is automatically compared and reconciled.
   - If the new field is numeric and should use tolerance, add it to the float branch in `_values_match()` (e.g. same as `net_worth`, `vat`, `gross_worth`).

After that, run `python main.py` and check `output.csv` and `comparison_report.csv` for the new column.

---

### 3.3 Changing or adding regex patterns (Pipeline B)

**Where:** `invoice_extractor/pipeline_b/structured_extractor.py`.

- **PATTERNS** is a dict: key = field name, value = list of regex patterns. `_first_match(text, patterns)` returns the first capturing group that matches.
- To improve extraction for a field, add or reorder patterns. More specific patterns should usually come first.
- Example — add a pattern for invoice number:
  ```python
  "invoice_number": [
      r"(?:invoice|factura|rechnung|nr|no\.?|number)\s*[#:]?\s*([A-Z0-9\-/]+)",
      r"Your new pattern here with one capturing group",
      # ...
  ],
  ```
- For numeric fields (`net_worth`, `vat`, `gross_worth`), the pattern should capture the number text; `_parse_number()` is used to convert to float.

---

### 3.4 Changing the LLM prompt (Pipeline A)

**Where:** `invoice_extractor/pipeline_a/llm_extractor.py`.

- **EXTRACTION_PROMPT** is the system/user prompt. It’s formatted with `{text}` (the OCR text).
- To add a field: add it to the “Required keys” list in the prompt with type (string/number) and ensure the field exists in `config.REQUIRED_FIELDS` and `models.InvoiceData` (see 3.2).
- To reduce hallucinations or change format: tighten the instructions (e.g. “Return only the JSON object, no markdown”) or add examples in the prompt.
- Token limit: the code uses `raw_text[:12000]`; you can change that if needed.

---

### 3.5 Changing reconciliation (which pipeline to prefer)

**Where:** `invoice_extractor/utils/validator.py`.

- **reconcile_value(field_name, pipeline_a_value, pipeline_b_value, prefer_b_on_mismatch=True)**  
  - If A and B match, either value is used (B preferred when not None).  
  - If they don’t match: when `prefer_b_on_mismatch=True` the reconciled value is B; when `False` it’s A.
- **build_reconciled_invoice()** calls `reconcile_value(..., prefer_b_on_mismatch=True)`. To prefer Pipeline A on mismatch, change that call to `prefer_b_on_mismatch=False`.
- You can also implement per-field preference (e.g. prefer A for `invoice_number`, B for `gross_worth`) by passing a map or adding logic inside `build_reconciled_invoice`.

---

### 3.6 Changing normalization rules

**Where:** `invoice_extractor/utils/normalizer.py`.

- **normalize_field(field_name, value)** dispatches by field name to:
  - `normalize_currency` (for `net_worth`, `vat`, `gross_worth`)
  - `normalize_date` (for `invoice_date`)
  - `normalize_tax_id` (for `seller_tax_id`, `client_tax_id`)
  - `normalize_name` (for `seller_name`, `client_name`)
  - `normalize_string` (for `invoice_number` and fallback)
- To change how a field is normalized:
  - Edit the corresponding normalizer function, or
  - Add a new set (e.g. `CUSTOM_FIELDS`) and a branch in `normalize_field()`.
- For a new field, add it to the appropriate set (see 3.2 step 5).

---

### 3.7 Changing comparison logic (when A and B “match”)

**Where:** `invoice_extractor/utils/validator.py`, function `_values_match()`.

- Float fields use `FLOAT_TOLERANCE` from config.
- String/date fields: comparison is `str(a).strip().lower() == str(b).strip().lower()`.
- To add a new numeric field with tolerance, include its name in the float branch in `_values_match()`. To compare differently (e.g. ignore punctuation), add a field-specific branch.

---

## 4. Running and testing

- **Full run:** From repo root, `python main.py` or `python -m invoice_extractor.main`.
- **Image set:** Control via `INVOICE_IMAGE_START` / `INVOICE_IMAGE_END` (e.g. `348`–`349` for two images).
- **Logs:** Logging is to stdout; level is INFO. Mismatches are logged per document.
- **Outputs:** Always check `invoice_extractor/outputs/output.csv` and `comparison_report.csv` after changes.

Suggested quick test: set `INVOICE_IMAGE_START` and `INVOICE_IMAGE_END` to a single image, run, and inspect the two CSVs and the printed summary.

---

## 5. Google Colab

- Use **`colab_setup.ipynb`**: it installs Tesseract and dependencies and runs the pipeline.
- In Colab you typically use **OpenAI** (`INVOICE_LLM_PROVIDER=openai`, `OPENAI_API_KEY`). Set the key in a cell or via Colab Secrets.
- You can point `INVOICE_IMAGES_DIR` to a Google Drive folder with invoice images.

---

## 6. Troubleshooting

| Issue | What to check |
|-------|----------------|
| “No images found” | `INVOICE_IMAGES_DIR`, `IMAGE_PREFIX`, `IMAGE_START`, `IMAGE_END`, `IMAGE_EXT`; file names must match `{PREFIX}{index:04d}.{EXT}`. |
| Pipeline A fails (LLM) | Ollama: is it running? `ollama list` / `ollama pull <model>`. OpenAI: `OPENAI_API_KEY` and `INVOICE_LLM_PROVIDER=openai`. |
| OCR fails | Tesseract installed and on PATH, or `TESSERACT_CMD` set correctly (Windows). |
| Missing or wrong column in CSV | Field must be in `config.REQUIRED_FIELDS`, in `models.InvoiceData`, and (for Pipeline B) in `extract_structured()`. |
| Comparison always “mismatch” for numbers | Check `normalizer` (same format for A and B) and `FLOAT_TOLERANCE` in `validator`. |
| Wrong reconciled value | `validator.build_reconciled_invoice` and `reconcile_value(..., prefer_b_on_mismatch=...)`. |

---

## 7. Checklist for adding a new field

- [ ] Add to `REQUIRED_FIELDS` in `config.py`
- [ ] Add to `InvoiceData` and `to_dict()` / `from_dict()` in `models.py`
- [ ] Add to Pipeline A prompt in `llm_extractor.py` (and ensure LLM returns it)
- [ ] Add extraction (patterns or heuristic) in `pipeline_b/structured_extractor.py`
- [ ] Add to the right normalizer set (and logic if needed) in `normalizer.py`
- [ ] If numeric with tolerance, add to float branch in `validator._values_match()`
- [ ] Run pipeline and verify column in `output.csv` and `comparison_report.csv`

---

## 8. Where to look for more

- **README.md** — Overview, requirements, installation, configuration table, usage, outputs, optional Ollama/Azure/Colab.
- **.env.example** — All supported env vars with short comments.
- **invoice_extractor/config.py** — Single source of truth for env defaults and `REQUIRED_FIELDS`.

Once you’ve run the pipeline once and opened `config.py`, `main.py`, and the two pipeline files, this guide’s “Making changes” section should be enough to implement most feature changes safely.
