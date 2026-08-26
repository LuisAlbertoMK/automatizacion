# SDD Tasks: P4-S1 — requests.Session Reuse

## Task 1: Create `src/utils/http_client.py`
- [ ] Implement `get_http_session()` singleton with HTTPAdapter + Retry
- [ ] Implement `close_http_session()`
- [ ] Module-level constants: _RETRY_STRATEGY, _ADAPTER

## Task 2: Create `tests/test_http_client.py`
- [ ] test_session_singleton — same instance returned
- [ ] test_retry_configured — adapter has Retry
- [ ] test_close_resets_session — close_http_session() resets

## Task 3: Update src/utils/captcha.py
- [ ] Add import: `from src.utils.http_client import get_http_session`
- [ ] Replace 5 sync calls (lines 49, 86, 126, 173, 303)
- [ ] Replace 4 async to_thread calls (lines 194-196, 212, 233, 262-266)
- [ ] Keep `import requests` for RequestException

## Task 4: Update src/tramites/base.py
- [ ] Add import
- [ ] Replace line 402 lambda

## Task 5: Update src/tramites/nss.py
- [ ] Add import
- [ ] Replace line 241 lambda

## Task 6: Update src/tramites/cedula_profesional.py
- [ ] Add import
- [ ] Replace line 113 lambda

## Task 7: Update src/tramites/acta_nacimiento.py
- [ ] Add import
- [ ] Remove local `import requests` (line 119)
- [ ] Replace line 121 to_thread call

## Task 8: Update test files
- [ ] tests/test_captcha.py — update ~30 patches
- [ ] tests/test_nss.py — update ~10 patches
- [ ] tests/test_cedula_profesional.py — update ~4 patches
- [ ] tests/test_base.py — update ~5 patches
- [ ] tests/test_acta_nacimiento.py — update ~2 patches

## Task 9: Verify
- [x] pytest tests/test_http_client.py tests/test_captcha.py -v
- [x] pytest tests/test_nss.py tests/test_cedula_profesional.py tests/test_base.py tests/test_acta_nacimiento.py -v
- [x] ruff check all changed files
- [x] 78/78 sync tests pass, 100% http_client coverage, 94.20% logger coverage
