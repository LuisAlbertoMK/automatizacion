"""Tests para modules/base.py — BaseModule, la fundación de todos los módulos."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from modules.base import OUTPUT_DIR, TIMEOUT, BaseModule  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def module():
    """BaseModule sin captcha solver ni OCR."""
    with patch("utils.ocr.OCRExtractor"):
        yield BaseModule(captcha_solver=None, use_ocr=False, name="TestModule")


@pytest.fixture
def module_with_ocr():
    """BaseModule con OCR cargado."""
    with patch("utils.ocr.OCRExtractor") as mock_ocr:
        mock_ocr.return_value = MagicMock()
        yield BaseModule(captcha_solver=None, use_ocr=True, name="OcrModule")


def _make_mock_locator(visible=True, count=1):
    """Crea un locator de Playwright mockeado."""
    loc = MagicMock()
    loc.count = AsyncMock(return_value=count)
    first = MagicMock()
    first.is_visible = AsyncMock(return_value=visible)
    first.fill = AsyncMock()
    first.click = AsyncMock()
    loc.first = first
    return loc


@pytest.fixture
def mock_page():
    """Playwright Page mockeada."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.locator = MagicMock(side_effect=lambda sel: _make_mock_locator())
    page.evaluate = AsyncMock(return_value="")
    page.content = AsyncMock(return_value="<html></html>")
    page.screenshot = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.wait_for_selector = AsyncMock(return_value=None)
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.wait_for_navigation = AsyncMock()
    return page


# ── Constants ─────────────────────────────────────────────────────────────────

class TestConstants:
    def test_output_dir_default(self):
        assert OUTPUT_DIR == Path(os.getenv("OUTPUT_DIR", "./output"))

    def test_timeout_default(self):
        assert TIMEOUT == int(os.getenv("TIMEOUT", "60")) * 1000


# ── __init__ ──────────────────────────────────────────────────────────────────

class TestInit:
    def test_default_init(self, module):
        assert module.name == "TestModule"
        assert module.solver is None
        assert module.use_ocr is False

    def test_init_with_captcha_solver(self):
        solver = MagicMock()
        with patch("utils.ocr.OCRExtractor"):
            m = BaseModule(captcha_solver=solver, use_ocr=False)
        assert m.solver == solver

    def test_init_with_ocr(self, module_with_ocr):
        assert module_with_ocr.use_ocr is True
        assert module_with_ocr.ocr is not None

    def test_init_without_ocr(self, module):
        assert module.use_ocr is False
        assert module.ocr is None


# ── Logging ───────────────────────────────────────────────────────────────────

class TestLogging:
    def test_log_basic(self, module, capsys):
        module.log("mensaje de test")
        captured = capsys.readouterr()
        assert "mensaje de test" in captured.out

    def test_log_with_logger(self, module):
        logger = MagicMock()
        module._logger = logger
        module.log("log via logger")
        logger.info.assert_called_once_with("log via logger")

    def test_debug_verbose(self, module, capsys):
        os.environ["VERBOSE"] = "true"
        module.debug("debug msg")
        captured = capsys.readouterr()
        assert "debug msg" in captured.out
        del os.environ["VERBOSE"]

    def test_debug_not_verbose(self, module, capsys):
        os.environ["VERBOSE"] = "false"
        module.debug("debug invisible")
        captured = capsys.readouterr()
        assert captured.out == ""
        del os.environ["VERBOSE"]

    def test_warn(self, module, capsys):
        module.warn("cuidado")
        captured = capsys.readouterr()
        assert "cuidado" in captured.out

    def test_error(self, module, capsys):
        module.error("se rompió")
        captured = capsys.readouterr()
        assert "se rompió" in captured.out


# ── Rate Limiting ─────────────────────────────────────────────────────────────

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_first_call_no_delay(self):
        """Primera llamada no espera."""
        import modules.base as base_mod
        base_mod._last_request_time = 0.0
        t0 = asyncio.get_event_loop().time()
        await base_mod._rate_limit()
        elapsed = asyncio.get_event_loop().time() - t0
        assert elapsed < 0.2

    @pytest.mark.asyncio
    async def test_sets_last_request_time(self):
        """Después de llamar, _last_request_time se actualiza."""
        import modules.base as base_mod
        base_mod._last_request_time = 0.0
        await base_mod._rate_limit()
        assert base_mod._last_request_time > 0


# ── Extractores HTML ──────────────────────────────────────────────────────────

class TestExtractFromHTML:
    def test_extract_curp_valida(self, module):
        html = "CURP: GALJ800101HDFXXXX0"
        assert module.extract_curp_from_html(html) == "GALJ800101HDFXXXX0"

    def test_extract_curp_none_when_not_found(self, module):
        assert module.extract_curp_from_html("no hay nada") is None

    def test_extract_curp_formato_invalido(self, module):
        assert module.extract_curp_from_html("ABC123") is None

    def test_extract_nss_valido(self, module):
        html = "NSS: 12345678901"
        assert module.extract_nss_from_html(html) == "12345678901"

    def test_extract_nss_none_when_not_found(self, module):
        assert module.extract_nss_from_html("sin nss") is None

    def test_extract_both_from_same_html(self, module):
        html = "CURP: GALJ800101HDFXXXX0 NSS: 98765432109"
        assert module.extract_curp_from_html(html) == "GALJ800101HDFXXXX0"
        assert module.extract_nss_from_html(html) == "98765432109"


# ── Fill Field ────────────────────────────────────────────────────────────────

class TestFillField:
    @pytest.mark.asyncio
    async def test_fill_first_selector_works(self, module, mock_page):
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(visible=True)
        result = await module.fill_field(mock_page, ["#campo"], "valor")
        assert result is True
        mock_page.locator.assert_called_with("#campo")

    @pytest.mark.asyncio
    async def test_fill_visible_check(self, module, mock_page):
        """Si el campo no es visible, no lo llena."""
        calls = 0
        def locator_side_effect(sel):
            nonlocal calls
            calls += 1
            if calls == 1:
                return _make_mock_locator(visible=False)
            return _make_mock_locator(visible=True)
        mock_page.locator.side_effect = locator_side_effect
        result = await module.fill_field(mock_page, ["#no", "#si"], "valor")
        assert result is True

    @pytest.mark.asyncio
    async def test_fill_all_invisible(self, module, mock_page):
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(visible=False)
        result = await module.fill_field(mock_page, ["#a", "#b"], "valor")
        assert result is False


# ── Click First ───────────────────────────────────────────────────────────────

class TestClickFirst:
    @pytest.mark.asyncio
    async def test_click_first_visible(self, module, mock_page):
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(visible=True)
        result = await module.click_first(mock_page, ["#btn"])
        assert result is True

    @pytest.mark.asyncio
    async def test_click_none_visible(self, module, mock_page):
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(visible=False)
        result = await module.click_first(mock_page, ["#btn"])
        assert result is False

    @pytest.mark.asyncio
    async def test_click_with_navigation(self, module, mock_page):
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(visible=True)
        mock_page.expect_navigation = MagicMock()
        mock_page.expect_navigation.return_value.__aenter__ = AsyncMock()
        mock_page.expect_navigation.return_value.__aexit__ = AsyncMock()
        result = await module.click_first(mock_page, ["#btn"], wait_nav=True)
        assert result is True


# ── Debug Screenshot ──────────────────────────────────────────────────────────

class TestDebugScreenshot:
    @pytest.mark.asyncio
    async def test_screenshot_not_taken_when_headless(self, module, mock_page):
        """HEADLESS=true por defecto → no screenshot."""
        with patch("modules.base.HEADLESS", True):
            await module.debug_screenshot(mock_page, "test.png")
        mock_page.screenshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_screenshot_taken_when_visible(self, module, mock_page):
        with patch("modules.base.HEADLESS", False):
            await module.debug_screenshot(mock_page, "test.png")
        mock_page.screenshot.assert_called_once()


# ── Open PDF ──────────────────────────────────────────────────────────────────

class TestOpenPDF:
    @patch("platform.system", return_value="Windows")
    @patch("os.startfile")
    def test_open_pdf_windows(self, mock_startfile, mock_platform, module):
        module.open_pdf(Path("test.pdf"))
        mock_startfile.assert_called_once_with("test.pdf")

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_open_pdf_darwin(self, mock_run, mock_platform, module):
        module.open_pdf(Path("test.pdf"))
        mock_run.assert_called_once_with(["open", "test.pdf"])

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_open_pdf_linux(self, mock_run, mock_platform, module):
        module.open_pdf(Path("test.pdf"))
        mock_run.assert_called_once_with(["xdg-open", "test.pdf"])

    @patch("platform.system", return_value="Windows")
    @patch("os.startfile")
    def test_open_pdf_failure_does_not_crash(self, mock_startfile, mock_platform, module, capsys):
        mock_startfile.side_effect = Exception("No hay visor PDF")
        module.open_pdf(Path("test.pdf"))  # no debe crashear
        captured = capsys.readouterr()
        assert "No hay visor PDF" in captured.out or "abrir" in captured.out


# ── Detect Site Key ───────────────────────────────────────────────────────────

class TestDetectSiteKey:
    @pytest.mark.asyncio
    async def test_detect_from_data_sitekey(self, module, mock_page):
        mock_page.evaluate = AsyncMock(return_value="SITE_KEY_123")
        result = await module.detect_site_key(mock_page)
        assert result == "SITE_KEY_123"

    @pytest.mark.asyncio
    async def test_detect_from_script_content(self, module, mock_page):
        mock_page.evaluate = AsyncMock(return_value=None)
        mock_page.content = AsyncMock(
            return_value='<div data-sitekey="SITE_FROM_ATTR"></div>'
        )
        result = await module.detect_site_key(mock_page)
        assert result == "SITE_FROM_ATTR"

    @pytest.mark.asyncio
    async def test_detect_returns_none_when_not_found(self, module, mock_page):
        mock_page.evaluate = AsyncMock(return_value=None)
        mock_page.content = AsyncMock(return_value="<html></html>")
        result = await module.detect_site_key(mock_page)
        assert result is None


# ── Inject reCAPTCHA Token ────────────────────────────────────────────────────

class TestInjectRecaptcha:
    @pytest.mark.asyncio
    async def test_inject_token(self, module, mock_page):
        mock_page.evaluate = AsyncMock()
        await module.inject_recaptcha_token(mock_page, "TOKEN_XYZ")
        call_arg = mock_page.evaluate.call_args[0][0]
        assert "g-recaptcha-response" in call_arg
        assert '"TOKEN_XYZ"' in call_arg


# ── Wait for reCAPTCHA ────────────────────────────────────────────────────────

class TestWaitRecaptcha:
    @pytest.mark.asyncio
    async def test_wait_recaptcha_resolved(self, module, mock_page):
        """Devuelve True si se resuelve."""
        mock_page.evaluate = AsyncMock(return_value="a" * 30)  # len > 20
        with patch("modules.base.asyncio.sleep"):
            result = await module.wait_for_recaptcha(mock_page, max_wait=10)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_recaptcha_timeout(self, module, mock_page):
        """Timeout devuelve False."""
        mock_page.evaluate = AsyncMock(return_value="")
        with patch("modules.base.asyncio.sleep"):
            result = await module.wait_for_recaptcha(mock_page, max_wait=1)
        assert result is False


# ── Goto ──────────────────────────────────────────────────────────────────────

class TestGoto:
    @pytest.mark.asyncio
    async def test_goto_normal(self, module, mock_page):
        mock_page.goto = AsyncMock()
        with patch("modules.base._rate_limit", AsyncMock()):
            with patch("modules.base.asyncio.sleep"):
                await module.goto(mock_page, "https://example.com")
        mock_page.goto.assert_called_once()

    @pytest.mark.asyncio
    async def test_goto_fallback(self, module, mock_page):
        mock_page.goto = AsyncMock(side_effect=[Exception("fail"), None])
        with patch("modules.base._rate_limit", AsyncMock()):
            with patch("modules.base.asyncio.sleep"):
                await module.goto(mock_page, "https://primary.com", fallback_url="https://fallback.com")
        assert mock_page.goto.call_count == 2


# ── Browser ───────────────────────────────────────────────────────────────────

class TestBrowser:
    @pytest.mark.asyncio
    async def test_launch_browser_structure(self, module):
        """Verifica que launch_browser retorna (p, browser, page)."""
        mock_pw = AsyncMock()
        mock_firefox = MagicMock()
        mock_firefox.launch = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.new_context = AsyncMock()
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = MagicMock()
        mock_firefox.launch.return_value = mock_browser
        mock_pw.firefox = mock_firefox

        with patch("modules.base.async_playwright", return_value=mock_pw):
            p, browser, page = await module.launch_browser()
            assert p is not None
            assert browser is not None
            assert page is not None

    @pytest.mark.asyncio
    async def test_close_browser(self, module):
        p = AsyncMock()
        browser = MagicMock()
        browser.close = AsyncMock()
        await module.close_browser(p, browser)
        browser.close.assert_awaited_once()
        p.__aexit__.assert_awaited_once()
