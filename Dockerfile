FROM python:3.12-slim

WORKDIR /app

# ── System deps ────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    firefox-esr \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ────────────────────────────────────────────
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright browsers ────────────────────────────────────
RUN playwright install firefox

# ── App ────────────────────────────────────────────────────
COPY . .
RUN pip install -e . --no-deps 2>/dev/null || true

# ── Health check ───────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
  CMD python health_check.py --quick || exit 1

# ── Run ────────────────────────────────────────────────────
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
