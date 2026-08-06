"""Tests unitarios para BrowserPool — pool de browsers Firefox."""
import time
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

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_failure_stop_tambien_falla(self, mock_async_playwright):
        """Cleanup: stop() lanza → except + logger.debug (94-95)."""
        mocks = _make_async_playwright_mock(mock_browsers=[AsyncMock()])

        def fail_on_first(*args, **kwargs):
            raise RuntimeError("browser launch failed")

        mocks[1].firefox.launch = AsyncMock(side_effect=fail_on_first)
        mocks[1].stop = AsyncMock(side_effect=RuntimeError("stop failed"))
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1)
        with patch("src.utils.browser_pool.logger") as mock_logger:
            with pytest.raises(RuntimeError, match="browser launch failed"):
                await pool.initialize()

        mock_logger.debug.assert_called_once()
        assert pool._initialized is False


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
    async def test_acquire_relaunch_browser_inactivo(self, mock_async_playwright):
        """acquire con browser inactivo → relaunch FUERA del lock (94-95)."""
        b1, b2, b3 = AsyncMock(), AsyncMock(), AsyncMock()
        mocks = _make_async_playwright_mock(mock_browsers=[b1, b2, b3])
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=2, idle_timeout=1)
        await pool.initialize()
        pool._last_used[b1] = 0  # b1 quedó inactivo

        browser = await pool.acquire()

        assert browser is b3  # se relanzó (no reusó b1 ni b2)
        b1.close.assert_awaited_once()  # el inactivo se cerró
        assert pool._last_used[b3] > 0

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


class TestCloseIdleBrowser:
    """_close_idle_browser() — cierre de browsers inactivos."""

    @pytest.mark.asyncio
    async def test_cierra_inactivo(self):
        pool = BrowserPool(pool_size=1, idle_timeout=10)
        browser = AsyncMock()
        pool._last_used[browser] = 0  # inactivo desde hace mucho

        result = await pool._close_idle_browser(browser)

        assert result is True
        browser.close.assert_awaited_once()
        assert browser not in pool._last_used

    @pytest.mark.asyncio
    async def test_no_cierra_reciente(self):
        pool = BrowserPool(pool_size=1, idle_timeout=300)
        browser = AsyncMock()
        pool._last_used[browser] = time.time()

        result = await pool._close_idle_browser(browser)

        assert result is False
        browser.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_close_no_propaga(self):
        """browser.close() lanza → se registra debug y se limpia igual."""
        pool = BrowserPool(pool_size=1, idle_timeout=10)
        browser = AsyncMock()
        browser.close = AsyncMock(side_effect=RuntimeError("boom"))
        pool._last_used[browser] = 0
        with patch("src.utils.browser_pool.logger") as mock_logger:
            result = await pool._close_idle_browser(browser)
        assert result is True
        mock_logger.debug.assert_called_once()
        assert browser not in pool._last_used


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


class TestBrowserPoolLifecycle:
    """P1: max_uses, health check (is_connected), stats."""

    def test_max_uses_default(self):
        pool = BrowserPool()
        assert pool.max_uses == 10

    def test_max_uses_custom(self):
        pool = BrowserPool(max_uses=5)
        assert pool.max_uses == 5

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_usage_count_initialized(self, mock_async_playwright):
        """New browsers start with usage_count = 0."""
        mock_browser = AsyncMock()
        mock_browser.is_connected = True
        mocks = _make_async_playwright_mock(mock_browsers=[mock_browser])
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1)
        await pool.initialize()
        assert pool._usage_count[mock_browser] == 0

    @pytest.mark.asyncio
    async def test_check_lifecycle_disconnected(self):
        """Returns True (relaunch) when is_connected is False."""
        pool = BrowserPool(max_uses=10)
        mock_browser = AsyncMock()
        mock_browser.is_connected = False
        result = await pool._check_lifecycle(mock_browser)
        assert result is True
        mock_browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_lifecycle_max_uses(self):
        """Returns True when usage_count >= max_uses."""
        pool = BrowserPool(max_uses=3)
        mock_browser = AsyncMock()
        mock_browser.is_connected = True
        pool._usage_count[mock_browser] = 3
        result = await pool._check_lifecycle(mock_browser)
        assert result is True
        mock_browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_lifecycle_healthy(self):
        """Returns False when browser connected + under max_uses."""
        pool = BrowserPool(max_uses=10)
        mock_browser = AsyncMock()
        mock_browser.is_connected = True
        pool._usage_count[mock_browser] = 1
        result = await pool._check_lifecycle(mock_browser)
        assert result is False
        mock_browser.close.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_release_increments_count(self, mock_async_playwright):
        """release() increments _usage_count."""
        mock_browser = AsyncMock()
        mock_browser.is_connected = True
        mocks = _make_async_playwright_mock(mock_browsers=[mock_browser])
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1, max_uses=10)
        await pool.initialize()
        browser = await pool._pool.get()
        await pool.release(browser)
        assert pool._usage_count[browser] == 1
        assert pool._pool.qsize() == 1

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_acquire_relaunches_on_disconnect(self, mock_async_playwright):
        """acquire() relaunches when browser is disconnected."""
        mock_old = AsyncMock()
        mock_old.is_connected = False
        mock_new = AsyncMock()
        mock_new.is_connected = True
        mocks = _make_async_playwright_mock(
            mock_browsers=[mock_old, mock_new]
        )
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1, max_uses=10)
        await pool.initialize()
        browser = await pool.acquire()
        assert browser is mock_new
        assert pool._usage_count[browser] == 0

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_acquire_relaunches_on_max_uses(self, mock_async_playwright):
        """acquire() relaunches when max_uses exceeded."""
        mock_old = AsyncMock()
        mock_old.is_connected = True
        mock_new = AsyncMock()
        mock_new.is_connected = True
        mocks = _make_async_playwright_mock(
            mock_browsers=[mock_old, mock_new]
        )
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1, max_uses=1)
        await pool.initialize()
        b1 = await pool.acquire()
        await pool.release(b1)  # usage_count → 1, meets max_uses
        b2 = await pool.acquire()  # should relaunch
        assert b2 is mock_new
        assert pool._usage_count[b2] == 0

    def test_stats_property(self):
        """stats returns correct dict."""
        pool = BrowserPool(pool_size=3, max_uses=10)
        stats = pool.stats
        assert stats["pool_size"] == 3
        assert stats["max_uses"] == 10
        assert stats["initialized"] is False
        assert stats["tracked_browsers"] == 0

    @pytest.mark.asyncio
    @patch("src.utils.browser_pool.async_playwright")
    async def test_close_clears_usage_count(self, mock_async_playwright):
        """close() clears _usage_count."""
        mock_browser = AsyncMock()
        mock_browser.is_connected = True
        mocks = _make_async_playwright_mock(mock_browsers=[mock_browser])
        mock_async_playwright.return_value = mocks[0].return_value

        pool = BrowserPool(pool_size=1)
        await pool.initialize()
        pool._usage_count = {mock_browser: 3}
        await pool.close()
        assert pool._usage_count == {}
