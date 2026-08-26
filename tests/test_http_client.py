"""Tests para utils/http_client.py — singleton session with pooling + retries."""

from src.utils.http_client import (
    _ADAPTER,
    _RETRY_STRATEGY,
    close_http_session,
    get_http_session,
)


class TestGetHttpSession:
    def test_returns_session_instance(self):
        close_http_session()
        session = get_http_session()
        import requests as req
        assert isinstance(session, req.Session)

    def test_singleton_same_instance(self):
        """get_http_session() always returns the same instance (singleton)."""
        close_http_session()
        s1 = get_http_session()
        s2 = get_http_session()
        assert s1 is s2

    def test_adapter_mounted(self):
        """HTTPAdapter mounted on both http:// and https://."""
        close_http_session()
        session = get_http_session()
        assert isinstance(session.get_adapter("http://example.com"), _ADAPTER.__class__)
        assert isinstance(session.get_adapter("https://example.com"), _ADAPTER.__class__)


class TestRetryStrategy:
    def test_retry_total_is_3(self):
        assert _RETRY_STRATEGY.total == 3

    def test_backoff_factor_is_0_5(self):
        assert _RETRY_STRATEGY.backoff_factor == 0.5

    def test_status_forcelist_has_5xx(self):
        assert 500 in _RETRY_STRATEGY.status_forcelist
        assert 502 in _RETRY_STRATEGY.status_forcelist
        assert 503 in _RETRY_STRATEGY.status_forcelist
        assert 504 in _RETRY_STRATEGY.status_forcelist


class TestCloseHttpSession:
    def test_close_resets_singleton(self):
        """close_http_session() → next call returns new instance."""
        close_http_session()
        s1 = get_http_session()
        close_http_session()
        s2 = get_http_session()
        assert s1 is not s2

    def test_close_idempotent(self):
        """Calling close when no session exists is safe."""
        close_http_session()
        close_http_session()  # no error
        assert get_http_session() is not None
        close_http_session()
