"""Tests para src/tramites/base.py — BaseModule, la fundación de todos los módulos."""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tramites.base import OUTPUT_DIR, TIMEOUT, BaseModule, BrowserResources  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def module():
    """BaseModule sin captcha solver ni OCR."""
    with (
        patch("src.utils.ocr.OCRExtractor"),
        patch("src.utils.logger.get_logger", return_value=None),
    ):
        yield BaseModule(captcha_solver=None, use_ocr=False, name="TestModule")


@pytest.fixture
def module_with_ocr():
    """BaseModule con OCR cargado."""
    with (
        patch("src.utils.ocr.OCRExtractor") as mock_ocr,
        patch("src.utils.logger.get_logger", return_value=None),
    ):
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
    first.get_attribute = AsyncMock(return_value="http://example.com/img.png")
    first.text_content = AsyncMock(return_value="")
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
        with (
            patch("src.utils.ocr.OCRExtractor"),
            patch("src.utils.logger.get_logger", return_value=None),
        ):
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

    def test_debug_with_logger(self, module):
        """Line 358: _logger.debug."""
        logger = MagicMock()
        module._logger = logger
        module.debug("debug via logger")
        logger.debug.assert_called_once_with("debug via logger")

    def test_warn_with_logger(self, module):
        """Line 365: _logger.warn."""
        logger = MagicMock()
        module._logger = logger
        module.warn("warn via logger")
        logger.warn.assert_called_once_with("warn via logger")

    def test_error_with_logger(self, module):
        """Line 372: _logger.error."""
        logger = MagicMock()
        module._logger = logger
        module.error("error via logger")
        logger.error.assert_called_once_with("error via logger")


# ── Rate Limiting ─────────────────────────────────────────────────────────────

class TestRateLimit:
    @pytest.mark.asyncio
    async def test_first_call_no_delay(self):
        """Primera llamada no espera."""
        import src.tramites.base as base_mod
        base_mod._last_request_time = 0.0
        t0 = asyncio.get_event_loop().time()
        await base_mod._rate_limit()
        elapsed = asyncio.get_event_loop().time() - t0
        assert elapsed < 0.2

    @pytest.mark.asyncio
    async def test_sets_last_request_time(self):
        """Después de llamar, _last_request_time se actualiza."""
        import src.tramites.base as base_mod
        base_mod._last_request_time = 0.0
        await base_mod._rate_limit()
        assert base_mod._last_request_time > 0

    @pytest.mark.asyncio
    async def test_second_call_within_window_waits(self):
        """Line 33: if elapsed < REQUEST_DELAY, sleeps."""
        import src.tramites.base as base_mod
        base_mod._last_request_time = 100.0
        old_delay = base_mod.REQUEST_DELAY
        base_mod.REQUEST_DELAY = 10.0
        with patch("src.tramites.base.time.time", return_value=105.0):
            with patch("src.tramites.base.asyncio.sleep", AsyncMock()) as mock_sleep:
                await base_mod._rate_limit()
                mock_sleep.assert_awaited_once_with(5.0)
        base_mod.REQUEST_DELAY = old_delay


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

    @pytest.mark.asyncio
    async def test_click_pw_timeout_returns_true(self, module, mock_page):
        """Lines 136-138: PwTimeout en navigation, sigue.
        __aexit__ debe retornar None/falsy para NO suprimir la excepción."""
        from playwright.async_api import TimeoutError as PwTimeout
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        loc.first.is_visible = AsyncMock(return_value=True)
        loc.first.click = AsyncMock(side_effect=PwTimeout("timeout"))
        mock_page.locator.side_effect = lambda sel: loc
        mock_page.expect_navigation = MagicMock()
        mock_page.expect_navigation.return_value.__aenter__ = AsyncMock()
        mock_page.expect_navigation.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await module.click_first(mock_page, ["#btn"], wait_nav=True)
        assert result is True


# ── Resolve Image Captcha ──────────────────────────────────────────────────────

class TestResolveImageCaptcha:
    """Lines 146-198: resolve_image_captcha branches."""

    def _make_loc(self, count=1, src="http://example.com/captcha.png"):
        """Helper: locator personalizado para resolve_image_captcha."""
        loc = MagicMock()
        loc.count = AsyncMock(return_value=count)
        first = MagicMock()
        first.get_attribute = AsyncMock(return_value=src)
        loc.first = first
        return loc

    @pytest.mark.asyncio
    async def test_no_captcha_detected(self, module, mock_page):
        """Line 157: sin CAPTCHA de imagen → False."""
        mock_page.locator.side_effect = lambda sel: self._make_loc(count=0)
        result = await module.resolve_image_captcha(mock_page, ["#captcha-img"], ["#captcha-input"])
        assert result is False

    @pytest.mark.asyncio
    async def test_no_src_attribute(self, module, mock_page):
        """Line 163-164: imagen sin src → False."""
        mock_page.locator.side_effect = lambda sel: self._make_loc(src=None)
        result = await module.resolve_image_captcha(mock_page, ["#captcha-img"], ["#captcha-input"])
        assert result is False

    @pytest.mark.asyncio
    async def test_download_fails(self, module, mock_page):
        """Line 177-179: error descargando CAPTCHA → False."""
        mock_page.locator.side_effect = lambda sel: self._make_loc()
        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Connection error")
            result = await module.resolve_image_captcha(mock_page, ["#captcha-img"], ["#captcha-input"])
        assert result is False

    @pytest.mark.asyncio
    async def test_solver_resolves(self, module, mock_page):
        """Line 183-185: solver resuelve → fill_field."""
        mock_page.locator.side_effect = lambda sel: self._make_loc()
        solver = MagicMock()
        solver.solve_image.return_value = "ABC123"
        module.solver = solver
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(content=b"img_data")
            with patch.object(module, "fill_field", AsyncMock(return_value=True)) as mock_fill:
                result = await module.resolve_image_captcha(mock_page, ["#captcha-img"], ["#captcha-input"])
        assert result is True
        mock_fill.assert_awaited_once_with(mock_page, ["#captcha-input"], "ABC123")

    @pytest.mark.asyncio
    async def test_solver_fails_env_var_fallback(self, module, mock_page):
        """Lines 189-192: solver falla, CAPTCHA_VALUE env (DEBUG mode) → fill_field."""
        mock_page.locator.side_effect = lambda sel: self._make_loc()
        solver = MagicMock()
        solver.solve_image.side_effect = Exception("Solver fail")
        module.solver = solver
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(content=b"img_data")
            with patch("src.tramites.base.os.getenv") as mock_env:
                mock_env.side_effect = lambda k, d="": {"DEBUG": "true", "CAPTCHA_VALUE": "ENV_VAL"}.get(k, d)
                with patch.object(module, "fill_field", AsyncMock(return_value=True)) as mock_fill:
                    result = await module.resolve_image_captcha(mock_page, ["#captcha-img"], ["#captcha-input"])
        assert result is True
        mock_fill.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_solution_nowhere(self, module, mock_page):
        """Lines 194-196: sin solución → False."""
        mock_page.locator.side_effect = lambda sel: self._make_loc()
        module.solver = None
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(content=b"img_data")
            with patch("src.tramites.base.os.getenv", return_value=""):
                result = await module.resolve_image_captcha(mock_page, ["#captcha-img"], ["#captcha-input"])
        assert result is False

    @pytest.mark.asyncio
    async def test_relative_src_constructs_full_url(self, module, mock_page):
        """Lines 166-169: src relativa → construye URL completa."""
        mock_page.locator.side_effect = lambda sel: self._make_loc(src="/captcha/img.png")
        mock_page.url = "https://gob.mx/tramite"
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(content=b"img_data")
            with patch.object(module, "fill_field", AsyncMock(return_value=False)):
                await module.resolve_image_captcha(mock_page, ["#captcha-img"], ["#captcha-input"])
        mock_get.assert_called_once()
        args, _ = mock_get.call_args
        assert args[0] == "https://gob.mx/captcha/img.png"


# ── Debug Screenshot ──────────────────────────────────────────────────────────

class TestDebugScreenshot:
    @pytest.mark.asyncio
    async def test_screenshot_not_taken_when_headless(self, module, mock_page):
        """HEADLESS=true por defecto → no screenshot."""
        with patch("src.tramites.base.HEADLESS", True):
            await module.debug_screenshot(mock_page, "test.png")
        mock_page.screenshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_screenshot_taken_when_visible(self, module, mock_page):
        with patch("src.tramites.base.HEADLESS", False):
            await module.debug_screenshot(mock_page, "test.png")
        mock_page.screenshot.assert_called_once()


# ── Find Visible Inputs ───────────────────────────────────────────────────────

class TestFindVisibleInputs:
    """Lines 327-336: find_visible_inputs."""

    @pytest.mark.asyncio
    async def test_finds_visible_inputs(self, module, mock_page):
        """Encuentra inputs visibles."""
        async def get_attr(name):
            return {"name": "curp", "id": "", "placeholder": ""}.get(name, "")
        inp1 = MagicMock()
        inp1.is_visible = AsyncMock(return_value=True)
        inp1.get_attribute = get_attr
        inp2 = MagicMock()
        inp2.is_visible = AsyncMock(return_value=False)
        inp2.get_attribute = AsyncMock(return_value="")
        mock_page.query_selector_all = AsyncMock(return_value=[inp1, inp2])
        result = await module.find_visible_inputs(mock_page)
        assert len(result) == 1
        assert result[0]["name"] == "curp"

    @pytest.mark.asyncio
    async def test_filters_by_keyword(self, module, mock_page):
        """Filtra inputs por keyword."""
        async def get_attr(name):
            return {"name": "curp_input", "id": "", "placeholder": ""}.get(name, "")
        inp = MagicMock()
        inp.is_visible = AsyncMock(return_value=True)
        inp.get_attribute = get_attr
        mock_page.query_selector_all = AsyncMock(return_value=[inp])
        result = await module.find_visible_inputs(mock_page, keyword="curp")
        assert len(result) == 1
        # keyword no match
        result2 = await module.find_visible_inputs(mock_page, keyword="nss")
        assert len(result2) == 0


# ── Open PDF ──────────────────────────────────────────────────────────────────

class TestOpenPDF:
    @patch("platform.system", return_value="Windows")
    @patch("os.startfile")
    def test_open_pdf_windows(self, mock_startfile, mock_platform, module):
        with patch("src.tramites.base.HEADLESS", False):
            module.open_pdf(Path("test.pdf"))
        mock_startfile.assert_called_once_with("test.pdf")

    @patch("platform.system", return_value="Darwin")
    @patch("subprocess.run")
    def test_open_pdf_darwin(self, mock_run, mock_platform, module):
        with patch("src.tramites.base.HEADLESS", False):
            module.open_pdf(Path("test.pdf"))
        mock_run.assert_called_once_with(["open", "test.pdf"])

    @patch("platform.system", return_value="Linux")
    @patch("subprocess.run")
    def test_open_pdf_linux(self, mock_run, mock_platform, module):
        with patch("src.tramites.base.HEADLESS", False):
            module.open_pdf(Path("test.pdf"))
        mock_run.assert_called_once_with(["xdg-open", "test.pdf"])

    @patch("platform.system", return_value="Windows")
    @patch("os.startfile")
    def test_open_pdf_failure_does_not_crash(self, mock_startfile, mock_platform, module, capsys):
        mock_startfile.side_effect = Exception("No hay visor PDF")
        with patch("src.tramites.base.HEADLESS", False):
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

    @pytest.mark.asyncio
    async def test_detect_from_json_in_content(self, module, mock_page):
        """Line 238: sitekey vía regex en script JSON."""
        mock_page.evaluate = AsyncMock(return_value=None)
        mock_page.content = AsyncMock(
            return_value='<script>{"sitekey": "JSON_KEY_123"}</script>'
        )
        result = await module.detect_site_key(mock_page)
        assert result == "JSON_KEY_123"


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
        with patch("src.tramites.base.asyncio.sleep"):
            result = await module.wait_for_recaptcha(mock_page, max_wait=10)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_recaptcha_timeout(self, module, mock_page):
        """Timeout devuelve False."""
        mock_page.evaluate = AsyncMock(return_value="")
        with patch("src.tramites.base.asyncio.sleep"):
            result = await module.wait_for_recaptcha(mock_page, max_wait=1)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_recaptcha_prints_every_10s(self, module, mock_page, capsys):
        """Line 220: print cada 10s de espera."""
        # Retorna vacío 11 veces (22s a interval 2s), timeout en 20s
        mock_page.evaluate = AsyncMock(return_value="")
        with patch("src.tramites.base.asyncio.sleep"):
            await module.wait_for_recaptcha(mock_page, max_wait=20)
        captured = capsys.readouterr()
        # Debería imprimir status a los ~10s y ~20s (múltiplos de 10)
        assert "Esperando..." in captured.out


# ── Download PDF ──────────────────────────────────────────────────────────────

class TestDownloadPDF:
    """Lines 263-308: download_pdf with selector, fallback, and failure paths."""

    @pytest.fixture
    def mock_download(self):
        dl = MagicMock()
        dl.save_as = AsyncMock()
        return dl

    class _AsyncContextMock:
        """Context manager async mock con __aenter__/__aexit__ en la clase."""
        def __init__(self, enter_return):
            self._enter_return = enter_return
        async def __aenter__(self):
            return self._enter_return
        async def __aexit__(self, *args):
            pass

    def _make_expect_download(self, mock_download):
        """Crea context manager + info para page.expect_download.
        info.value debe ser un objeto coroutine (await info.value, no info.value()).
        __aenter__/__aexit__ van en la clase (no instancia) por protocolo."""
        async def _val():
            return mock_download
        info = MagicMock()
        info.value = _val()  # coroutine object
        return self._AsyncContextMock(info)

    @pytest.mark.asyncio
    async def test_download_via_selector(self, module, mock_page, mock_download):
        """Line 271-277: descarga exitosa por selector."""
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(count=1, visible=True)
        mock_page.expect_download.return_value = self._make_expect_download(mock_download)
        with patch.object(module, "open_pdf"):
            result = await module.download_pdf(mock_page, ["#btn"], Path("out.pdf"))
        assert result == Path("out.pdf")
        mock_download.save_as.assert_awaited_once_with(Path("out.pdf"))

    @pytest.mark.asyncio
    async def test_download_via_selector_fails_then_fallback(self, module, mock_page, mock_download):
        """Lines 278-280: inner except en selector, fallback succeed."""
        mock_page.locator = MagicMock()  # reset side_effect
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        loc.first = MagicMock()
        loc.first.is_visible = AsyncMock(return_value=True)
        loc.first.click = AsyncMock(side_effect=Exception("click fail"))
        mock_page.locator.side_effect = lambda sel: loc
        # Fallback link
        link = MagicMock()
        link.is_visible = AsyncMock(return_value=True)
        link.text_content = AsyncMock(return_value="descargar pdf")
        async def get_attr(name):
            return {"href": "/file.pdf", "onclick": ""}.get(name, "")
        link.get_attribute = get_attr
        link.click = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[link])
        mock_page.expect_download.return_value = self._make_expect_download(mock_download)
        with patch.object(module, "open_pdf"):
            result = await module.download_pdf(mock_page, ["#btn"], Path("out.pdf"))
        assert result == Path("out.pdf")

    @pytest.mark.asyncio
    async def test_selector_exception_fallback(self, module, mock_page, mock_download):
        """Line 278-280: selector falla → fallback con keywords."""
        # page.locator(sel) raises Exception → caught, fallback tried
        mock_page.locator.side_effect = Exception("nope")
        # Fallback link matches keyword "pdf"
        link = MagicMock()
        link.is_visible = AsyncMock(return_value=True)
        link.text_content = AsyncMock(return_value="Descargar PDF")
        async def get_attr(name):
            return {"href": "/file.pdf", "onclick": ""}.get(name, "")
        link.get_attribute = get_attr
        link.click = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[link])
        mock_page.expect_download.return_value = self._make_expect_download(mock_download)
        with patch.object(module, "open_pdf"):
            result = await module.download_pdf(mock_page, ["#btn"], Path("out.pdf"))
        assert result == Path("out.pdf")

    @pytest.mark.asyncio
    async def test_no_download_found_anywhere(self, module, mock_page):
        """Lines 307-308: sin botón de descarga → None."""
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(count=0)
        mock_page.query_selector_all = AsyncMock(return_value=[])
        result = await module.download_pdf(mock_page, ["#btn"], Path("out.pdf"))
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_exception_caught(self, module, mock_page):
        """Line 304-305: fallback exception → debug log."""
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(count=0)
        mock_page.query_selector_all = AsyncMock(side_effect=Exception("DOM error"))
        with patch("src.tramites.base.os.getenv", return_value="true"):  # VERBOSE
            result = await module.download_pdf(mock_page, ["#btn"], Path("out.pdf"))
        assert result is None


# ── Goto ──────────────────────────────────────────────────────────────────────

class TestGoto:
    @pytest.mark.asyncio
    async def test_goto_normal(self, module, mock_page):
        mock_page.goto = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()
        with patch("src.tramites.base._rate_limit", AsyncMock()):
            await module.goto(mock_page, "https://example.com")
        mock_page.goto.assert_called_once()
        mock_page.wait_for_timeout.assert_called_once()

    @pytest.mark.asyncio
    async def test_goto_fallback(self, module, mock_page):
        mock_page.goto = AsyncMock(side_effect=[Exception("fail"), None])
        mock_page.wait_for_timeout = AsyncMock()
        with patch("src.tramites.base._rate_limit", AsyncMock()):
            await module.goto(mock_page, "https://primary.com", fallback_url="https://fallback.com")
        assert mock_page.goto.call_count == 2
        mock_page.wait_for_timeout.assert_called_once()


# ── Browser ───────────────────────────────────────────────────────────────────

class TestBrowser:
    @pytest.mark.asyncio
    async def test_launch_browser_structure(self, module):
        """Verifica que launch_browser retorna BrowserResources."""
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

        with (
            patch("src.utils.browser_pool.get_browser_pool", return_value=None),
            patch("src.tramites.base.async_playwright", return_value=mock_pw),
        ):
            br = await module.launch_browser()
            assert isinstance(br, BrowserResources)
            assert br.browser is not None
            assert br.page is not None
            assert br._playwright is not None  # non-pool mode

    @pytest.mark.asyncio
    async def test_close_browser(self, module):
        br = AsyncMock(spec=BrowserResources)
        await module.close_browser(br)
        br.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_launch_via_pool(self, module):
        """Lines 157-171: launch_browser con pool exitoso."""
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context
        mock_pool = AsyncMock()
        mock_pool.acquire.return_value = mock_browser

        with patch("src.utils.browser_pool.get_browser_pool", return_value=mock_pool):
            br = await module.launch_browser()
        assert br._from_pool is True
        assert br._pool is mock_pool
        assert br.page is mock_page

    @pytest.mark.asyncio
    async def test_launch_with_sandbox(self, module):
        """Line 178: PLAYWRIGHT_NO_SANDBOX=true → --no-sandbox."""
        mock_pw = AsyncMock()
        mock_firefox = MagicMock()
        mock_firefox.launch = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page.return_value = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_firefox.launch.return_value = mock_browser
        mock_pw.firefox = mock_firefox
        mock_pw.__aenter__.return_value = mock_pw

        with (
            patch("src.utils.browser_pool.get_browser_pool", return_value=None),
            patch("src.tramites.base.async_playwright", return_value=mock_pw),
            patch.dict(os.environ, {"PLAYWRIGHT_NO_SANDBOX": "true"}),
        ):
            await module.launch_browser()
        args = mock_firefox.launch.call_args[1]
        assert "--no-sandbox" in args.get("args", [])


# ── BrowserResources.close ─────────────────────────────────────────────────

class TestBrowserResourcesClose:
    """Lines 50-71: error handlers en BrowserResources.close()."""

    @pytest.mark.asyncio
    async def test_context_close_fails(self, capsys):
        """Lines 53-54: _context.close() lanza → catch."""
        br = BrowserResources(
            browser=MagicMock(), page=MagicMock(),
            _context=AsyncMock(),
        )
        br._context.close = AsyncMock(side_effect=Exception("ctx close fail"))
        await br.close()
        captured = capsys.readouterr()
        assert "Error al cerrar context" in captured.out
        assert br._context is None  # se resetea pese al error

    @pytest.mark.asyncio
    async def test_pool_release_fails(self, capsys):
        """Lines 60-61: pool.release() lanza → catch."""
        mock_pool = AsyncMock()
        mock_pool.release = AsyncMock(side_effect=Exception("pool release fail"))
        br = BrowserResources(
            browser=MagicMock(), page=MagicMock(),
            _pool=mock_pool, _context=MagicMock(),
        )
        br._context.close = AsyncMock()
        await br.close()
        captured = capsys.readouterr()
        assert "Error al liberar browser al pool" in captured.out

    @pytest.mark.asyncio
    async def test_browser_close_fails(self, capsys):
        """Lines 65-66: browser.close() lanza → catch (sin pool)."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock(side_effect=Exception("browser close fail"))
        br = BrowserResources(
            browser=mock_browser, page=MagicMock(),
            _pool=None, _playwright=MagicMock(),
        )
        br._playwright.__aexit__ = AsyncMock()
        await br.close()
        captured = capsys.readouterr()
        assert "Error al cerrar browser" in captured.out

    @pytest.mark.asyncio
    async def test_playwright_exit_fails(self, capsys):
        """Lines 69-71: __aexit__() lanza → catch."""
        mock_pw = MagicMock()
        mock_pw.__aexit__ = AsyncMock(side_effect=Exception("pw exit fail"))
        br = BrowserResources(
            browser=MagicMock(), page=MagicMock(),
            _pool=None, _playwright=mock_pw,
        )
        await br.close()
        captured = capsys.readouterr()
        assert "Error al cerrar Playwright" in captured.out

    @pytest.mark.asyncio
    async def test_close_no_context_no_pool(self):
        """Sin _context ni _pool — solo browser.close."""
        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        br = BrowserResources(
            browser=mock_browser, page=MagicMock(),
            _pool=None, _playwright=None,
        )
        await br.close()
        mock_browser.close.assert_awaited_once()


# ── Init — custom interaction ──────────────────────────────────────────────

class TestInitCustomInteraction:
    def test_custom_interaction(self):
        """Line 125: interaction proporcionado → se usa."""
        mock_interaction = MagicMock()
        with (
            patch("src.utils.ocr.OCRExtractor"),
            patch("src.utils.logger.get_logger", return_value=None),
        ):
            m = BaseModule(
                captcha_solver=None, use_ocr=False,
                interaction=mock_interaction,
            )
        assert m.interaction is mock_interaction


# ── Goto — fallback que también falla ──────────────────────────────────────

class TestGotoFallbackFails:
    """Lines 246-248: goto con primary y fallback que fallan."""

    @pytest.mark.asyncio
    async def test_both_urls_fail(self, module, mock_page):
        from src.exceptions import ModuleError
        mock_page.goto = AsyncMock(side_effect=Exception("fail"))
        with patch("src.tramites.base._rate_limit", AsyncMock()):
            with pytest.raises(ModuleError, match="No se pudo navegar"):
                await module.goto(mock_page, "https://pri.com", fallback_url="https://fall.com")
        assert mock_page.goto.call_count == 2


# ── Fill Field — cache hit ─────────────────────────────────────────────────

class TestFillFieldCache:
    """Lines 266-273: fill_field con selector cacheado."""

    def _cache_key(self, selectors):
        return str(tuple(selectors))

    @pytest.mark.asyncio
    async def test_cache_hit(self, module, mock_page):
        key = self._cache_key(["input#test-cached"])
        module._selector_cache[key] = "input#test-cached"
        result = await module.fill_field(mock_page, ["input#test-cached"], "valor")
        assert result is True
        mock_page.locator.assert_called_with("input#test-cached")

    @pytest.mark.asyncio
    async def test_cache_hit_stale_goes_to_full_loop(self, module, mock_page):
        """Cache hit pero locator no visible → recae en full loop."""
        key = self._cache_key(["input#stale"])
        module._selector_cache[key] = "input#stale"
        calls = [0]
        def locator_side(sel):
            calls[0] += 1
            if calls[0] == 1:  # cache lookup falla por no visible
                loc = _make_mock_locator(visible=False)
                return loc
            return _make_mock_locator(visible=True)
        mock_page.locator.side_effect = locator_side
        result = await module.fill_field(mock_page, ["input#stale"], "val")
        assert result is True
        assert calls[0] >= 2  # full loop intentó el cached y luego fresh

    @pytest.mark.asyncio
    async def test_selector_raises_exception(self, module, mock_page):
        """Lines 289-291: locator lanza Exception → catch y continua."""
        def locator_side_effect(sel):
            if sel == "#falla":
                raise Exception("css inválido")
            return _make_mock_locator(visible=True)
        mock_page.locator.side_effect = locator_side_effect
        result = await module.fill_field(mock_page, ["#falla", "#ok"], "val")
        assert result is True


# ── Click First — cache hit ────────────────────────────────────────────────

class TestClickFirstCache:
    """Lines 298-311: click_first con selector cacheado."""

    def _cache_key(self, selectors):
        return str(tuple(selectors))

    @pytest.mark.asyncio
    async def test_cache_hit(self, module, mock_page):
        key = self._cache_key(["button#btn"])
        module._selector_cache[key] = "button#btn"
        result = await module.click_first(mock_page, ["button#btn"])
        assert result is True
        mock_page.locator.assert_called_with("button#btn")

    @pytest.mark.asyncio
    async def test_cache_hit_with_nav(self, module, mock_page):
        key = self._cache_key(["button#nav-btn"])
        module._selector_cache[key] = "button#nav-btn"
        mock_page.expect_navigation = MagicMock()
        mock_page.expect_navigation.return_value.__aenter__ = AsyncMock()
        mock_page.expect_navigation.return_value.__aexit__ = AsyncMock()
        result = await module.click_first(mock_page, ["button#nav-btn"], wait_nav=True)
        assert result is True

    @pytest.mark.asyncio
    async def test_selector_raises_exception(self, module, mock_page):
        """Lines 335-337: locator lanza Exception → catch y continua."""
        def locator_side_effect(sel):
            if sel == "#falla":
                raise Exception("bad selector")
            return _make_mock_locator(visible=True)
        mock_page.locator.side_effect = locator_side_effect
        result = await module.click_first(mock_page, ["#falla", "#ok"])
        assert result is True


# ── Clear Selector Cache ───────────────────────────────────────────────────

class TestClearCache:
    """Line 342: clear_selector_cache."""

    def test_clear_cache(self, module):
        module._selector_cache["a"] = "b"
        assert len(module._selector_cache) == 1
        module.clear_selector_cache()
        assert len(module._selector_cache) == 0


# ── Wait for reCAPTCHA — error path ────────────────────────────────────────

class TestWaitRecaptchaError:
    """Lines 427-428: evaluate() lanza Exception → catch."""

    @pytest.mark.asyncio
    async def test_evaluate_exception(self, module, mock_page):
        mock_page.evaluate = AsyncMock(side_effect=Exception("evaluate fail"))
        with patch("src.tramites.base.asyncio.sleep"):
            result = await module.wait_for_recaptcha(mock_page, max_wait=2)
        assert result is False


# ── Detect Site Key — error path ───────────────────────────────────────────

class TestDetectSiteKeyError:
    """Lines 449-450: page.content() lanza → catch."""

    @pytest.mark.asyncio
    async def test_content_raises(self, module, mock_page):
        mock_page.evaluate = AsyncMock(return_value=None)
        mock_page.content = AsyncMock(side_effect=Exception("DOM error"))
        result = await module.detect_site_key(mock_page)
        assert result is None


# ── Download PDF — fallback click error ────────────────────────────────────

class TestDownloadPDFFallbackError:
    """Lines 511-513: fallback click lanza → continue."""

    @pytest.mark.asyncio
    async def test_fallback_click_exception(self, module, mock_page):
        mock_loc = MagicMock()
        mock_loc.count = AsyncMock(return_value=0)
        mock_page.locator.side_effect = lambda sel: mock_loc
        # Fallback links: visible but click fails
        link = MagicMock()
        link.is_visible = AsyncMock(return_value=True)
        link.text_content = AsyncMock(return_value="descargar")
        link.get_attribute = MagicMock(side_effect=lambda name: {
            "href": "/file.pdf", "onclick": ""
        }.get(name, ""))
        link.click = AsyncMock(side_effect=Exception("click fail"))
        mock_page.query_selector_all = AsyncMock(return_value=[link])
        mock_page.expect_download.return_value.__aenter__ = AsyncMock()
        mock_page.expect_download.return_value.__aexit__ = AsyncMock()
        with patch.object(module, "debug"):
            result = await module.download_pdf(mock_page, ["#btn"], Path("out.pdf"))
        assert result is None

    @pytest.mark.asyncio
    async def test_fallback_link_not_visible(self, module, mock_page):
        """511-513: link no visible → continue al próximo."""
        mock_page.locator.side_effect = lambda sel: _make_mock_locator(count=0)
        link = MagicMock()
        link.is_visible = AsyncMock(return_value=False)
        link.text_content = AsyncMock(return_value="pdf")
        mock_page.query_selector_all = AsyncMock(return_value=[link])
        result = await module.download_pdf(mock_page, ["#btn"], Path("out.pdf"))
        assert result is None


# ── Open PDF — headless early return ───────────────────────────────────────

class TestOpenPDFHeadless:
    """Lines 523-524: HEADLESS=true → early return."""

    def test_headless_early_return(self, module):
        with patch("src.tramites.base.HEADLESS", True):
            with patch.object(module, "debug") as mock_debug:
                module.open_pdf(Path("test.pdf"))
        mock_debug.assert_called_once()
