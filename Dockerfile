FROM python:3.12-slim AS builder

WORKDIR /build

# ── Python deps ────────────────────────────────────────────
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# ── App install (no-deps since requirements.txt has it all) ──
COPY . .
RUN pip install -e . --no-deps


# ── Runtime stage ───────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# ── System deps (only Tesseract — Firefox via Playwright) ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# ── Copy installed packages from builder ──────────────────
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build /app

# ── Playwright browsers ────────────────────────────────────
RUN playwright install firefox

# ── Non-root user ──────────────────────────────────────────
RUN useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# ── Health check ───────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
  CMD python health_check.py --quick || exit 1

# ── Run ────────────────────────────────────────────────────
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
