# SDD Design: M5-S1 — Sanitize Tracebacks in Logging

## Architecture Decision

**Pattern**: Formatter wrapper (decorator pattern)  
**Approach**: Subclass `logging.Formatter` and override only `formatException()`. This is the single integration point Python's logging uses to format tracebacks.

## Implementation Design

### 1. New class: `SanitizingFormatter`

```python
class SanitizingFormatter(logging.Formatter):
    """Formatter that sanitizes PII from tracebacks (exc_info)."""

    def formatException(self, exc_info):
        """Override to sanitize PII from traceback before writing to log."""
        formatted = super().formatException(exc_info)
        return TramiteLogger._sanitize(formatted)
```

**Why `formatException`**: Python's `logging.Formatter.format()` calls `self.formatException(record.exc_info)` when `exc_info` is set. By overriding only this method, we sanitize tracebacks without touching the message formatting pipeline. The `_sanitize()` method is already a `@staticmethod` with `_PII_PATTERNS` — reusable.

**Why not override `format()`**: `format()` handles the full record (message + traceback). Overriding `formatException()` is more surgical — only the traceback portion is sanitized, and we don't need to reimplement the base `format()` logic.

### 2. Apply to file handler

In `TramiteLogger.__init__`, change:
```python
# Before:
fh.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))

# After:
fh.setFormatter(SanitizingFormatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
```

### 3. JSON formatter safety

Verify `JsonFormatter` doesn't include `exc_info` in output. Looking at the current implementation:
```python
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
```
It does NOT include `record.exc_info` or the formatted traceback. JSON format is already safe. ✅

### 4. Placement

`SanitizingFormatter` should be defined before `TramiteLogger` (since it references `TramiteLogger._sanitize`). Place it after the `JsonFormatter` class definition.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Performance overhead of sanitizing tracebacks | Low | Low | Only runs on errors; _sanitize is regex on short strings |
| Breaking existing log tests | Low | Low | SanitizingFormatter inherits from Formatter — same behavior minus sanitization |
| PII patterns miss edge cases | Medium | Medium | _PII_PATTERNS already covers CURP/NSS/email — proven in production |
