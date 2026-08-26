# SDD Spec: M5-S1 — Sanitize Tracebacks in Logging

**Proposal**: M5-S1

## Requirements

### REQ-1: SanitizingFormatter class
Add `SanitizingFormatter(logging.Formatter)` that overrides `formatException()` to pass traceback text through `TramiteLogger._sanitize()`.

### REQ-2: Apply to file handler
Replace `logging.Formatter(...)` with `SanitizingFormatter(...)` for the `RotatingFileHandler` in `TramiteLogger.__init__`.

### REQ-3: Traceback PII sanitization
When `exc_info=True` is passed to `logger.error()`, any PII (CURP, NSS, email) in the traceback text must be sanitized before writing to the log file.

### REQ-4: JSON format safety
`JsonFormatter` must not include unsanitized traceback data. (Verify it doesn't include exc_info — if it does, add sanitization.)

### REQ-5: Tests
- `test_traceback_sanitizes_curp`: Log with exc_info containing CURP in traceback → log file shows masked CURP
- `test_traceback_sanitizes_email`: Log with exc_info containing email → masked
- `test_traceback_sanitizes_nss`: Log with exc_info containing 11-digit NSS → masked

## Scenarios

### Scenario: Exception with PII in message is logged with exc_info
```
Given An exception message containing a CURP "481516070890123456"
When logger.error("Error CURP", exc_info=True) is called
Then the log file contains the error but CURP is masked as "4815****"
```

### Scenario: JSON format log
```
Given LOG_FORMAT=json
When An error with exc_info is logged
Then The JSON log entry does not contain PII in traceback field
```
