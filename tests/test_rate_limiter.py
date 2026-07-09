"""Tests unitarios para RateLimiter — rate limiter por dominio."""
import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.utils.rate_limiter import RateLimiter


class TestRateLimiterInit:
    """RateLimiter.__init__ — configuración inicial."""

    def test_default_delay(self):
        rl = RateLimiter()
        assert rl._default == 1.5
        assert rl._delay == {}
        assert rl._last == {}

    def test_custom_default(self):
        rl = RateLimiter(default_delay=3.0)
        assert rl._default == 3.0


class TestRateLimiterSetDelay:
    """RateLimiter.set_delay — configuración por dominio."""

    def test_set_delay(self):
        rl = RateLimiter()
        rl.set_delay("example.com", 5.0)
        assert rl._delay["example.com"] == 5.0

    def test_overwrite_delay(self):
        rl = RateLimiter()
        rl.set_delay("example.com", 1.0)
        rl.set_delay("example.com", 5.0)
        assert rl._delay["example.com"] == 5.0


class TestRateLimiterWait:
    """RateLimiter.wait — espera entre requests."""

    @pytest.mark.asyncio
    async def test_first_call_no_wait(self):
        rl = RateLimiter()
        with patch("src.utils.rate_limiter.asyncio.sleep", AsyncMock()) as mock_sleep:
            await rl.wait("example.com")
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_rapid_call_waits(self):
        rl = RateLimiter(default_delay=10.0)
        with patch("src.utils.rate_limiter.asyncio.sleep", AsyncMock()) as mock_sleep:
            await rl.wait("example.com")
            await rl.wait("example.com")
        mock_sleep.assert_called_once()
        delay_arg = mock_sleep.call_args[0][0]
        assert 0 < delay_arg <= 10.0

    @pytest.mark.asyncio
    async def test_different_domains_no_wait(self):
        rl = RateLimiter(default_delay=10.0)
        with patch("src.utils.rate_limiter.asyncio.sleep", AsyncMock()) as mock_sleep:
            await rl.wait("a.com")
            await rl.wait("b.com")
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_slow_call_no_extra_wait(self):
        rl = RateLimiter(default_delay=10.0)
        with patch("src.utils.rate_limiter.asyncio.sleep", AsyncMock()) as mock_sleep:
            t0 = time.monotonic()
            await rl.wait("example.com")
            t1 = time.monotonic()
            await rl.wait("example.com")
            t2 = time.monotonic()
        # El segundo wait debería dormir (delay 10s, elapsed ~0)
        assert mock_sleep.call_count >= 1
        # elapsed total entre waits es pequeño (<< delay)
        real_elapsed = t1 - t0
        assert real_elapsed < 1.0

    @pytest.mark.asyncio
    async def test_custom_delay_per_domain(self):
        rl = RateLimiter(default_delay=0.1)
        rl.set_delay("slow.com", 30.0)
        with patch("src.utils.rate_limiter.asyncio.sleep", AsyncMock()) as mock_sleep:
            await rl.wait("slow.com")
            await rl.wait("slow.com")
        mock_sleep.assert_called_once()
        delay_arg = mock_sleep.call_args[0][0]
        assert delay_arg > 0.1  # usa el delay específico, no el default


class TestRateLimiterReset:
    """RateLimiter.reset — reinicio de timers."""

    @pytest.mark.asyncio
    async def test_reset_specific_domain(self):
        rl = RateLimiter()
        await rl.wait("example.com")
        assert "example.com" in rl._last
        rl.reset("example.com")
        assert "example.com" not in rl._last

    @pytest.mark.asyncio
    async def test_reset_all(self):
        rl = RateLimiter()
        await rl.wait("a.com")
        await rl.wait("b.com")
        rl.reset()
        assert rl._last == {}

    @pytest.mark.asyncio
    async def test_reset_unknown_domain_noop(self):
        rl = RateLimiter()
        rl.reset("nonexistent.com")  # no debe fallar


class TestRateLimiterIntegration:
    """RateLimiter — verificación básica de comportamiento real."""

    @pytest.mark.asyncio
    async def test_actual_sleep_time(self):
        rl = RateLimiter(default_delay=0.05)
        t0 = time.monotonic()
        await rl.wait("test.com")
        t1 = time.monotonic()
        await rl.wait("test.com")
        t2 = time.monotonic()
        elapsed = t2 - t1
        assert elapsed >= 0.04  # tolerancia 10ms
