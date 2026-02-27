# Invoice extraction: Pipeline A (OCR + LLM) and Pipeline B (OCR + regex)
# Build from invoice_extractor/: docker build -f invoice_extractor/Dockerfile invoice_extractor
# Or from invoice_extractor/: docker build .
FROM python:3.11-slim

# Install Tesseract OCR (required by pytesseract)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-pol \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy package into /app/invoice_extractor so "python -m invoice_extractor.main" works
COPY . invoice_extractor/

# Run from /app with package on path
CMD ["python", "-m", "invoice_extractor.main"]
