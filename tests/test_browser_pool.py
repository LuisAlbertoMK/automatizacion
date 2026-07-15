"""Tests unitarios para BrowserPool — pool de browsers Firefox."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.browser_pool import BrowserPool, get_browser_pool, shutdown_browser_pool


@pytest.fixture(autouse=True)
def _reset_global_pool():
    """Resetea el singleton global del pool antes de cada test."""
    import src.utils.browser_pool as bp

    bp._pool_instance = None


def _make_async_playwright_mock(
    mock_browsers: list | None = None,
    launch_side_effect: Exception | None = None,
):
    """Helper: construye el árbol de mocks para async_playwright().start()."""
    mock_playwright = MagicMock()
    mock_firefox = MagicMock()

    if launch_side_effect:
        mock_firefox.launch = AsyncMock(side_effect=launch_side_effect)
    elif mock_browsers:
        mock_firefox.launch = AsyncMock(side_effect=mock_browsers)
    else:
        mock_browser = AsyncMock()
        mock_firefox.launch = AsyncMock(return_value=mock_browser)

    mock_playwright.firefox = mock_firefox
    mock_playwright.stop = AsyncMock()

    mock_ctx = MagicMock()
    mock_ctx.start = AsyncMock(return_value=mock_playwright)

    mock_async_playwright = MagicMock()
    mock_async_playwright.return_value = mock_ctx
    return mock_async_playwright, mock_playwright


class TestBrowserPoolInit:
    """BrowserPool.__init__ — configuración inicial."""

    def test_defaults(self):
        pool = BrowserPool()
        assert pool.pool_size == 2
        assert pool.idle_timeout == 300
        assert pool._pool is None
        assert pool._playwright is None
        assert pool._initialized is False
        assert pool._last_used == {}

    def test_custom_params(self):
        pool = BrowserPool(pool_size=5, idle_timeout=600)
        assert pool.pool_size == 5
        assert pool.idle_timeout == 600


class TestBrowserPoolInitialize:
    """BrowserPool.initialize() — lanzamiento de browsers."""

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_happy_path(self, mock_async_playwright):
        mock_browsers = [AsyncMock(), AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=2)
        await pool.initialize()

        assert pool._initialized is True
        assert pool._playwright is mocks[1]
        assert pool._pool is not None
        assert pool._pool.qsize() == 2
        for b in mock_browsers:
            assert b in pool._last_used

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_idempotent(self, mock_async_playwright):
        mock_browsers = [AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1)
        await pool.initialize()
        await pool.initialize()

        assert pool._initialized is True
        assert mocks[1].firefox.launch.call_count == 1

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_failure_cleans_up(self, mock_async_playwright):
        mock_browsers = [AsyncMock(), AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)

        def fail_on_second(*args, **kwargs):
            mock_browsers.pop(0)
            raise RuntimeError("browser launch failed")

        mocks[1].firefox.launch = AsyncMock(side_effect=fail_on_second)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=2)
        with pytest.raises(RuntimeError, match="browser launch failed"):
            await pool.initialize()

        assert pool._initialized is False
        assert pool._playwright is None
        assert pool._pool is None
        mocks[1].stop.assert_awaited_once()


class TestBrowserPoolAcquireRelease:
    """acquire() / release() — ciclo de vida de browsers."""

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_acquire(self, mock_async_playwright):
        mock_browsers = [AsyncMock(), AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=2)
        await pool.initialize()

        browser = await pool.acquire()

        assert browser in mock_browsers
        assert pool._pool.qsize() == 1
        assert pool._last_used[browser] > 0

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_acquire_auto_initializes(self, mock_async_playwright):
        mock_browser = AsyncMock()
        mocks = _make_async_playwright_mock(mock_browsers=[mock_browser])
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1)
        browser = await pool.acquire()

        assert pool._initialized is True
        assert browser is mock_browser

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_acquire_after_initialize_noop(self, mock_async_playwright):
        mock_browsers = [AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1)
        await pool.initialize()

        mocks[1].firefox.launch.reset_mock()
        await pool.acquire()

        mocks[1].firefox.launch.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_release(self, mock_async_playwright):
        mock_browsers = [AsyncMock(), AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=2)
        await pool.initialize()

        browser = await pool.acquire()
        before = pool._pool.qsize()
        await pool.release(browser)

        assert pool._pool.qsize() == before + 1
        assert pool._last_used[browser] > 0

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_acquire_release_cycle(self, mock_async_playwright):
        mock_browsers = [AsyncMock(), AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=2)
        await pool.initialize()

        b1 = await pool.acquire()
        b2 = await pool.acquire()
        assert pool._pool.qsize() == 0

        await pool.release(b1)
        await pool.release(b2)
        assert pool._pool.qsize() == 2


class TestBrowserPoolClose:
    """close() — shutdown completo."""

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_close(self, mock_async_playwright):
        mock_browsers = [AsyncMock(), AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=2)
        await pool.initialize()

        await pool.close()

        assert pool._initialized is False
        assert pool._last_used == {}
        for b in mock_browsers:
            b.close.assert_awaited_once()
        mocks[1].stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_not_initialized(self):
        pool = BrowserPool()
        await pool.close()

        assert pool._initialized is False
        assert pool._playwright is None
        assert pool._pool is None

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_close_idempotent(self, mock_async_playwright):
        mock_browsers = [AsyncMock()]
        mocks = _make_async_playwright_mock(mock_browsers=mock_browsers)
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1)
        await pool.initialize()
        await pool.close()
        await pool.close()

        mocks[1].stop.assert_awaited_once()


class TestBrowserPoolSingleton:
    """get_browser_pool() / shutdown_browser_pool() — singleton global."""

    def test_get_browser_pool_singleton(self):
        p1 = get_browser_pool()
        p2 = get_browser_pool()
        assert p1 is p2

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_shutdown_browser_pool(self, mock_async_playwright):
        mock_browser = AsyncMock()
        mocks = _make_async_playwright_mock(mock_browsers=[mock_browser])
        mock_async_playwright.return_value = mocks[0].return_value

        pool = get_browser_pool()
        pool.pool_size = 1
        await pool.initialize()
        await shutdown_browser_pool()

        assert pool._initialized is False
        new_pool = get_browser_pool()
        assert new_pool is not pool

    @pytest.mark.asyncio
    async def test_shutdown_browser_pool_noop_when_none(self):
        import src.utils.browser_pool as bp

        bp._pool_instance = None
        await shutdown_browser_pool()
