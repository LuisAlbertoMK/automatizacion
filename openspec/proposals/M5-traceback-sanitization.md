# SDD Proposal: M5 — Sanitize Tracebacks in Logging

**ID**: M5-S1  
**Date**: 2026-08-26  
**Status**: PROPOSED  
**Gap from**: analysis v2, item M5 (ICE 1.6)

## Intent

Prevent PII leakage via `exc_info=True` tracebacks in log files. Currently, `TramiteLogger.error(msg, exc_info=True)` sanitizes the message string but Python's logging framework appends the raw traceback (which may contain PII from exception messages) to the log output without sanitization.

## Scope

### In
- `src/utils/logger.py` — Add `SanitizingFormatter` that overrides `formatException()`
- `tests/test_logger.py` — Add tests for traceback sanitization
- `docs/mejoras/` — Update analysis (mark M5 → FIXED)

### Out
- No changes to `src/api.py` (the `exc_info=True` calls remain; fix is at formatter level)
- No changes to any tramite modules
- No changes to log message sanitization (already works)

## Approach

1. Create `SanitizingFormatter(logging.Formatter)` that wraps `formatException()` output through `TramiteLogger._sanitize()`
2. Use `SanitizingFormatter` for the `RotatingFileHandler` (text format)
3. JSON formatter (`JsonFormatter`) doesn't include exc_info in output — already safe
4. Add unit tests for tracebacks containing CURP/NSS/email patterns
