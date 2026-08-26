# SDD Design: P4-S1 — requests.Session Reuse

## Architecture Decision

**Pattern**: Singleton Session with factory function  
**Rationale**: Single shared `requests.Session` with configured `HTTPAdapter` (connection pooling + retries). Avoids connection-per-call overhead. Thread-safe for read operations.

## Implementation Design

### 1. `src/utils/http_client.py`

```python
"""HTTP client with connection pooling via requests.Session singleton."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_http_session: requests.Session | None = None

# Retry config: exponential backoff on 5xx, connection errors
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
)

# Pool config: 10 connections, 20 max per host
_ADAPTER = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=_RETRY_STRATEGY,
)


def get_http_session() -> requests.Session:
    """Returns the shared HTTP session (singleton).

    The session has connection pooling and retry strategy configured.
    Thread-safe — requests.Session is safe for concurrent reads.
    """
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        _http_session.mount("http://", _ADAPTER)
        _http_session.mount("https://", _ADAPTER)
    return _http_session


def close_http_session() -> None:
    """Closes and resets the singleton session (mainly for tests)."""
    global _http_session
    if _http_session is not None:
        _http_session.close()
        _http_session = None
```

### 2. Source file update pattern

Each file adds import:
```python
from src.utils.http_client import get_http_session
```

Each call site pattern replacement:
```python
# Before:
r = requests.get(url, params=..., timeout=10)
r = requests.post(url, data=..., timeout=30)
resp = await asyncio.to_thread(requests.get, url, timeout=30)
resp = await loop.run_in_executor(None, lambda: requests.get(url, timeout=15, headers={...}))

# After:
r = get_http_session().get(url, params=..., timeout=10)
r = get_http_session().post(url, data=..., timeout=30)
resp = await asyncio.to_thread(get_http_session().get, url, timeout=30)
resp = await loop.run_in_executor(None, lambda: get_http_session().get(url, timeout=15, headers={...}))
```

**Key insight**: `asyncio.to_thread(get_http_session().get, url, timeout=30)` works because `get_http_session().get` returns a bound method.

### 3. Test update pattern

```python
# Before:
@patch("src.utils.captcha.requests.get")
def test_xxx(self, mock_get):
    mock_get.return_value.text = "5.5000"

# After:
@patch("src.utils.captcha.get_http_session")
def test_xxx(self, mock_session_factory):
    mock_session = MagicMock()
    mock_session_factory.return_value = mock_session
    mock_session.get.return_value.text = "5.5000"
```

### 4. Why not monkey-patch `requests`?

Monkey-patching `requests.get` globally would affect all code (including test runners, other libraries). The factory function approach is clean, testable, and scoped.

### 5. Thread safety

`requests.Session` is thread-safe for `get()`/`post()` calls after initialization. The singleton is created once. No race condition concern for the typical use case (single-threaded main loop + asyncio to_thread).
