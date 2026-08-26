# SDD Spec: P4-S1 — requests.Session Reuse

**Proposal**: P4-S1

## Requirements

### REQ-1: http_client module with singleton session
Create `src/utils/http_client.py` with:
- `get_http_session() -> requests.Session` — returns configured singleton
- Config: HTTPAdapter with `pool_connections=10`, `pool_maxsize=20`, `Retry(total=3, backoff_factor=0.5, status_forcelist=[500,502,503,504])`
- `close_http_session() -> None` — for testing cleanup

### REQ-2: Update captcha.py
Replace all `requests.get/post(...)` with `get_http_session().get/post(...)`:
- `_verify_balance()`: line 49
- `solve_image()`: line 86
- `solve_recaptcha_v2()`: line 126
- `solve_recaptcha_v3()`: line 173
- `_wait_for_result()`: line 303
- `solve_image_async()`: line 194-196 (to_thread)
- `solve_recaptcha_v2_async()`: line 212 (to_thread)
- `solve_recaptcha_v3_async()`: line 233 (to_thread)
- `_wait_for_result_async()`: line 262-266 (to_thread)
Keep `import requests` for `requests.RequestException`.

### REQ-3: Update tramites/base.py
- `requests.get(src, ...)` → `get_http_session().get(src, ...)`

### REQ-4: Update tramites/nss.py
- `requests.get(src, ...)` → `get_http_session().get(src, ...)`

### REQ-5: Update tramites/cedula_profesional.py
- `requests.get(SOLR_URL, ...)` → `get_http_session().get(SOLR_URL, ...)`

### REQ-6: Update tramites/acta_nacimiento.py
- Remove local `import requests` (line 119)
- `asyncio.to_thread(requests.get, pdf_url, timeout=30)` → `asyncio.to_thread(get_http_session().get, pdf_url, timeout=30)`

### REQ-7: Update tests
- `test_captcha.py`: `@patch("src.utils.captcha.requests.get")` → `@patch("src.utils.captcha.get_http_session")` with mock session
- Same pattern for test_nss, test_cedula_profesional, test_base, test_acta_nacimiento
- Add `test_http_client.py` — test session singleton + retry config

### REQ-8: Backward compat
- `requests.RequestException` still raised (Session uses same exception hierarchy)
- `asyncio.to_thread(session.get, url, timeout=N)` works (bound method)

## Scenarios

### Scenario: Session is singleton
```
Given get_http_session() called twice
Then Both calls return the same Session instance
And The Session has Retry adapter mounted
```

### Scenario: Connection pooling works
```
Given Multiple calls to get_http_session().get()
Then All use the same TCP connection pool
And Retries are applied for 5xx responses
```

## Test Plan

| Test | File | Expected |
|------|------|----------|
| test_session_singleton | test_http_client.py | Same instance returned |
| test_retry_configured | test_http_client.py | Adapter has Retry with 3 retries |
| test_close_resets_session | test_http_client.py | close_http_session() → new session |
| All existing captcha tests | test_captcha.py | Pass with updated mocks |
| All existing nss tests | test_nss.py | Pass with updated mocks |
| All existing cedula tests | test_cedula_profesional.py | Pass with updated mocks |
| All existing base tests | test_base.py | Pass with updated mocks |
| All existing acta_nacimiento tests | test_acta_nacimiento.py | Pass with updated mocks |
