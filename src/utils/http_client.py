"""
utils/http_client.py — HTTP client with connection pooling via requests.Session singleton.

Provides a shared Session with:
  - Connection pooling (pool_connections=10, pool_maxsize=20)
  - Retry strategy (3 retries, exponential backoff on 5xx)

Usage:
    from src.utils.http_client import get_http_session
    r = get_http_session().get(url, params=..., timeout=30)
    r = get_http_session().post(url, data=..., timeout=30)

Thread-safe: requests.Session is safe for concurrent requests after init.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_http_session: requests.Session | None = None

# Retry: exponential backoff on 5xx, 3 total attempts
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
)

# Pool: 10 connection pools, 20 connections per pool
_ADAPTER = HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=_RETRY_STRATEGY,
)


def get_http_session() -> requests.Session:
    """Returns the shared HTTP session (singleton).

    The session has connection pooling and retry strategy configured.
    Thread-safe — requests.Session handles concurrent requests safely.
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
