FROM python:3.12-slim AS builder

WORKDIR /build

# ── Python deps (lock file para builds reproducibles) ─────
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# ── App install (no-deps since requirements.lock has it all) ──
COPY pyproject.toml ./
COPY src/ src/
COPY app.py main.py health_check.py benchmark_browser_pool.py ./
RUN pip install -e . --no-deps


# ── Runtime stage ───────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# ── System deps (only Tesseract — Firefox via Playwright) ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Copy installed packages from builder ──────────────────
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build /app

# ── Non-root user ──────────────────────────────────────────
RUN useradd --create-home --uid 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# ── Playwright browsers ────────────────────────────────────
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.cache
RUN playwright install firefox

# ── Health check ───────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
  CMD python health_check.py --quick || exit 1

# ── Run ────────────────────────────────────────────────────
ENTRYPOINT ["tramites"]
CMD ["--help"]
