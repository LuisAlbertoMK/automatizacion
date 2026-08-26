# SDD Tasks: M5-S1 — Sanitize Tracebacks in Logging

## Task 1: Add SanitizingFormatter class to logger.py
- [ ] Define `SanitizingFormatter(logging.Formatter)` with `formatException()` override
- [ ] Place after `JsonFormatter`, before `TramiteLogger`

## Task 2: Apply SanitizingFormatter to file handler
- [ ] Replace `logging.Formatter(...)` with `SanitizingFormatter(...)` in `__init__`

## Task 3: Verify JsonFormatter safety
- [ ] Confirm JSON format doesn't include exc_info in output (already verified — no change needed)

## Task 4: Add test for CURP sanitization in traceback
- [ ] In test_logger.py, test that logging with exc_info containing CURP masks it

## Task 5: Add test for email sanitization in traceback
- [ ] Test that email in traceback is masked

## Task 6: Add test for NSS sanitization in traceback
- [ ] Test that 11-digit NSS in traceback is masked

## Task 7: Verify
- [ ] `pytest tests/test_logger.py -v --cov=src.utils.logger --cov-report=term-missing`
- [ ] `ruff check src/utils/logger.py tests/test_logger.py`
- [ ] Coverage ≥ 90%
