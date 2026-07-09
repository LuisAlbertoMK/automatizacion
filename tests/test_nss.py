"""Tests para src/tramites/nss.py — NSS IMSS."""

import re
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import TimeoutError as PwTimeout

from src.exceptions import NSSError
from src.tramites.nss import NSSModule, RECAPTCHA_SITE_KEY_FALLBACK

# IMSCaptchaSolver se importa lazy dentro del módulo; pre-seed para que
# los parches `@patch("captcha_solver_imss.IMSCaptchaSolver")` funguen.
# El solve por defecto retorna fallback (como si no hubiera solver).
class _FakeIMSSolver:
    def solve(self, img_bytes):
        return {"success": False, "score": 0, "value": ""}


_captcha_mock = MagicMock()
_captcha_mock.IMSCaptchaSolver = MagicMock(return_value=_FakeIMSSolver())
sys.modules["captcha_solver_imss"] = _captcha_mock


def _setup_happy_nss(mock_base, prefill_content=True):
    """Configura mocks para flujo exitoso de NSS.

    _obtener_nss necesita page.content con 11 dígitos para encontrar el NSS.
    _enviar_formulario usa click_first (ya mockeado en conftest como True).
    """
    if prefill_content:
        mock_base['page'].content.return_value = (
            "<html><body>NSS = 98765432101</body></html>"
        )


class TestConsultar:
    async def test_sin_curp(self):
        mod = NSSModule()
        with pytest.raises(NSSError, match="Se requieren CURP y correo"):
            await mod.consultar(curp="", correo="a@b.com")

    async def test_sin_correo(self):
        mod = NSSModule()
        with pytest.raises(NSSError, match="Se requieren CURP y correo"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="")

    async def test_exitoso(self, mock_base):
        """Happy path con CURP + correo."""
        _setup_happy_nss(mock_base)
        mod = NSSModule()
        r = await mod.consultar(
            curp="GALJ800101HDFXXXX0", correo="test@test.com"
        )
        assert r["nss"] is not None
        assert r["curp"] == "GALJ800101HDFXXXX0"
        assert r["correo"] == "test@test.com"

    async def test_error_wrapper(self, mock_base):
        """Exception genérica → NSSError wrapper."""
        mock_base['goto'].side_effect = ValueError("connection refused")
        mod = NSSModule()
        with pytest.raises(NSSError, match="Error durante la consulta"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")

    async def test_nss_error_re_raise(self, mock_base):
        """NSSError dentro de _run → re-lanzada."""
        mock_base['goto'].side_effect = NSSError("específico")
        mod = NSSModule()
        with pytest.raises(NSSError, match="específico"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")


class TestEsperarFormulario:
    async def test_ok(self, mock_base):
        """wait_for_selector encuentra form → ok."""
        _setup_happy_nss(mock_base)
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_timeout_then_found(self, mock_base):
        """Primer selector timeout, segundo encuentra."""
        mock_base['page'].wait_for_selector = AsyncMock(side_effect=[
            PwTimeout("timeout"), None,  # primero timeout, segundo ok
        ])
        _setup_happy_nss(mock_base)
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_mantenimiento(self, mock_base):
        """Timeout + contenido 'mantenimiento' → NSSError."""
        mock_base['page'].wait_for_selector = AsyncMock(side_effect=PwTimeout("timeout"))
        mock_base['page'].content.return_value = (
            "<html>El portal está en mantenimiento</html>"
        )
        mod = NSSModule()
        with pytest.raises(NSSError, match="portal IMSS está en mantenimiento"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")


class TestIngresarCurp:
    async def test_ok(self, mock_base):
        _setup_happy_nss(mock_base)
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_fill_falla(self, mock_base):
        """fill_field falla → find_visible_inputs fallback."""
        _setup_happy_nss(mock_base)
        mock_base['fill_field'].return_value = False
        inp = {"name": "curp", "element": MagicMock()}
        inp["element"].fill = AsyncMock()
        inp_correo = {"element": MagicMock()}
        inp_correo["element"].fill = AsyncMock()
        # side_effect: _ingresar_curp → [inp], _ingresar_correo → [inp_correo]
        mock_base['find_visible_inputs'].side_effect = [[inp], [inp_correo]]

        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        inp["element"].fill.assert_called_once_with("GALJ800101HDFXXXX0")

    async def test_todo_falla(self, mock_base):
        """fill_field + find_visible fallan → NSSError."""
        mock_base['fill_field'].return_value = False
        mock_base['find_visible_inputs'].return_value = []

        mod = NSSModule()
        with pytest.raises(NSSError, match="No se encontró el campo CURP"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")


class TestIngresarCorreo:
    async def test_ok(self, mock_base):
        _setup_happy_nss(mock_base)
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_fill_falla(self, mock_base):
        """fill_field falla → find_visible_inputs con keyword correo."""
        _setup_happy_nss(mock_base)
        mock_base['fill_field'].return_value = False
        inp_curp = {"element": MagicMock()}
        inp_curp["element"].fill = AsyncMock()
        inp_correo = {"element": MagicMock()}
        inp_correo["element"].fill = AsyncMock()
        mock_base['find_visible_inputs'].side_effect = [
            [inp_curp],    # _ingresar_curp (keyword="curp")
            [inp_correo],  # _ingresar_correo (keyword="correo")
        ]

        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        inp_correo["element"].fill.assert_called_once_with("a@b.com")

    async def test_fill_falla_keyword_email(self, mock_base):
        """fill_field falla + find_visible('correo') vacío → fallback 'email'."""
        _setup_happy_nss(mock_base)
        mock_base['fill_field'].return_value = False
        inp_correo = {"element": MagicMock()}
        inp_correo["element"].fill = AsyncMock()
        inp_email = {"element": MagicMock()}
        inp_email["element"].fill = AsyncMock()
        mock_base['find_visible_inputs'].side_effect = [
            [inp_correo],  # _ingresar_curp (keyword="curp")
            [],            # _ingresar_correo (keyword="correo") → vacío
            [inp_email],   # _ingresar_correo (keyword="email") → fallback
        ]

        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_todo_falla(self, mock_base):
        """Ningún campo encontrado → NSSError."""
        mock_base['fill_field'].return_value = False
        mock_base['find_visible_inputs'].side_effect = [
            [{"element": MagicMock(fill=AsyncMock())}],  # _ingresar_curp ok
            [],  # _ingresar_correo (keyword="correo")
            [],  # _ingresar_correo (keyword="email")
        ]

        mod = NSSModule()
        with pytest.raises(NSSError, match="No se encontró el campo de correo"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")


class TestIngresarConfirmacionCorreo:
    async def test_ok(self, mock_base):
        """Confirmación encontrada."""
        _setup_happy_nss(mock_base)
        mock_base['fill_field'].return_value = True
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_sin_campo(self, mock_base):
        """Sin campo de confirmación → debug + continúa."""
        _setup_happy_nss(mock_base)
        mock_base['fill_field'].return_value = False
        inp_element = {"element": MagicMock()}
        inp_element["element"].fill = AsyncMock()
        # find_visible_inputs necesaria para curp y correo; confirmación usa solo fill_field
        mock_base['find_visible_inputs'].side_effect = [
            [{"element": MagicMock(fill=AsyncMock())}],  # _ingresar_curp
            [{"element": MagicMock(fill=AsyncMock())}],  # _ingresar_correo (keyword="correo")
        ]
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None


class TestResolverCaptchaImagen:
    async def test_sin_captcha(self, mock_base):
        """No hay img captcha en página → return."""
        _setup_happy_nss(mock_base)
        mock_base['page'].query_selector = AsyncMock(return_value=None)
        mod = NSSModule()
        result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert result is not None

    async def test_sin_input_captcha(self, mock_base):
        """Hay img pero no input captcha → return."""
        _setup_happy_nss(mock_base)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/CaptchaServlet?id=1")
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, None])
        mod = NSSModule()
        result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert result is not None

    async def test_img_sin_src(self, mock_base):
        """img sin atributo src → return."""
        _setup_happy_nss(mock_base)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="")
        inp = MagicMock()
        mock_base['page'].query_selector = AsyncMock(return_value=img)
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mod = NSSModule()
        result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert result is not None

    @patch("src.tramites.nss.requests.get")
    async def test_ims_solver_ok(self, mock_get, mock_base):
        """IMSCaptchaSolver resuelve con score ≥ 0.5."""
        _setup_happy_nss(mock_base, prefill_content=False)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/CaptchaServlet?id=1")
        inp = MagicMock()
        inp.fill = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake_image_bytes"

        with patch("captcha_solver_imss.IMSCaptchaSolver") as MockSolver:
            solver_instance = MagicMock()
            solver_instance.solve.return_value = {
                "success": True, "value": "ABC123",
                "score": 0.85, "engine": "ensemble",
            }
            MockSolver.return_value = solver_instance

            mod = NSSModule()
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            assert result is not None

    @patch("src.tramites.nss.requests.get")
    async def test_ims_solver_bajo_score(self, mock_get, mock_base):
        """IMSCaptchaSolver score < 0.5 → warn + fallback."""
        _setup_happy_nss(mock_base, prefill_content=False)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/CaptchaServlet?id=1")
        inp = MagicMock()
        inp.fill = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake"

        with patch("captcha_solver_imss.IMSCaptchaSolver") as MockSolver:
            solver_instance = MagicMock()
            solver_instance.solve.return_value = {
                "success": True, "value": "AB12",
                "score": 0.3, "engine": "tesseract",
            }
            MockSolver.return_value = solver_instance

            mod = NSSModule()
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            assert result is not None

    @patch("src.tramites.nss.requests.get")
    async def test_free_captcha_fallback(self, mock_get, mock_base):
        """IMSCaptchaSolver falla → FreeCaptchaSolver.solve_image intenta."""
        _setup_happy_nss(mock_base, prefill_content=False)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/Captcha?id=x")
        inp = MagicMock()
        inp.fill = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake"
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        with patch("captcha_solver_imss.IMSCaptchaSolver") as MockSolver:
            MockSolver.side_effect = ImportError("no module")
            solver = MagicMock()
            solver.solve_image.return_value = "FREE999"
            mod = NSSModule(captcha_solver=solver)
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            assert result is not None

    @patch("src.tramites.nss.requests.get")
    async def test_debug_env_captcha(self, mock_get, mock_base, monkeypatch):
        """DEBUG=true + CAPTCHA_VALUE → usa valor de entorno."""
        _setup_happy_nss(mock_base, prefill_content=False)
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("CAPTCHA_VALUE", "DEBUG123")

        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/Captcha?id=x")
        inp = MagicMock()
        inp.fill = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake"
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        with patch("captcha_solver_imss.IMSCaptchaSolver") as MockSolver:
            MockSolver.side_effect = ImportError("no module")

            mod = NSSModule()
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            assert result is not None

    @patch("src.tramites.nss.requests.get")
    async def test_download_exception(self, mock_get, mock_base):
        """requests.get falla → warn + return."""
        _setup_happy_nss(mock_base, prefill_content=False)
        mock_get.side_effect = Exception("timeout")

        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/Captcha?id=x")
        inp = MagicMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        mod = NSSModule()
        result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert result is not None

    @patch("src.tramites.nss.requests.get")
    async def test_ims_solver_exception(self, mock_get, mock_base):
        """IMSCaptchaSolver.solve lanza excepción → warn + fallback."""
        _setup_happy_nss(mock_base, prefill_content=False)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/Captcha?id=x")
        inp = MagicMock()
        inp.fill = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake"
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        with patch("captcha_solver_imss.IMSCaptchaSolver") as MockSolver:
            solver_instance = MagicMock()
            solver_instance.solve.side_effect = ValueError("solver crash")
            MockSolver.return_value = solver_instance

            mod = NSSModule()
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            assert result is not None

    @patch("src.tramites.nss.requests.get")
    async def test_sin_captcha_valor(self, mock_get, mock_base):
        """Ningún solver produce valor → warn + continuar."""
        _setup_happy_nss(mock_base, prefill_content=False)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/Captcha?id=x")
        inp = MagicMock()
        inp.fill = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake"
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        with patch("captcha_solver_imss.IMSCaptchaSolver") as MockSolver:
            MockSolver.side_effect = ImportError("no module")

            mod = NSSModule(captcha_solver=None)  # no solver at all
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            assert result is not None

    async def test_captcha_img_con_src_relativo(self, mock_base):
        """src relativo → completa URL."""
        _setup_happy_nss(mock_base, prefill_content=False)
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value="/CaptchaServlet?id=1")
        inp = MagicMock()
        inp.fill = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(side_effect=[img, inp])
        mock_base['page'].content.return_value = "<html>NSS 12345678901</html>"

        with patch("src.tramites.nss.requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = b""
            mod = NSSModule()
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            assert result is not None
            # Verificar que la URL se completó
            url_used = mock_get.call_args[0][0]
            assert url_used.startswith("https://serviciosdigitales.imss.gob.mx")


class TestResolverRecaptcha:
    async def test_sin_recaptcha(self, mock_base):
        """detect_site_key=None → return."""
        _setup_happy_nss(mock_base)
        mock_base['detect_site_key'].return_value = None
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_recaptcha_con_audio(self, mock_base):
        """solver con solve_recaptcha_v2_audio → token."""
        _setup_happy_nss(mock_base)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"

        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = AsyncMock(return_value="TOKEN456")
        mod = NSSModule(captcha_solver=solver)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None
        solver.solve_recaptcha_v2_audio.assert_called_once()

    async def test_recaptcha_audio_falla(self, mock_base):
        """Audio devuelve MANUAL → fallback a wait_for_recaptcha."""
        _setup_happy_nss(mock_base)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"

        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = AsyncMock(return_value="MANUAL")
        mod = NSSModule(captcha_solver=solver)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_recaptcha_auto_mode(self, mock_base, monkeypatch):
        """RECAPTCHA_AUTO=true → solve_recaptcha_v2."""
        _setup_happy_nss(mock_base)
        monkeypatch.setenv("RECAPTCHA_AUTO", "true")
        mock_base['detect_site_key'].return_value = "6Lc_xxx"

        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = None  # skip audio
        solver.solve_recaptcha_v2 = MagicMock(return_value="AUTO_TOKEN")
        mod = NSSModule(captcha_solver=solver)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None
        solver.solve_recaptcha_v2.assert_called_once()

    async def test_recaptcha_auto_token_manual(self, mock_base, monkeypatch):
        """RECAPTCHA_AUTO=true pero token=MANUAL → wait_for_recaptcha."""
        _setup_happy_nss(mock_base)
        monkeypatch.setenv("RECAPTCHA_AUTO", "true")
        mock_base['detect_site_key'].return_value = "6Lc_xxx"

        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = None  # skip audio
        solver.solve_recaptcha_v2 = MagicMock(return_value="MANUAL")
        mod = NSSModule(captcha_solver=solver)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_recaptcha_manual_mode(self, mock_base):
        """RECAPTCHA_AUTO=false → wait_for_recaptcha."""
        _setup_happy_nss(mock_base)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"

        solver = MagicMock()
        solver.solve_recaptcha_v2_audio = None  # skip audio
        mod = NSSModule(captcha_solver=solver)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_recaptcha_sin_solver(self, mock_base):
        """Sin solver configurado → wait_for_recaptcha."""
        _setup_happy_nss(mock_base)
        mock_base['detect_site_key'].return_value = "6Lc_xxx"
        mod = NSSModule(captcha_solver=None)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None
        mock_base['wait_for_recaptcha'].assert_called_once()


class TestEnviarFormulario:
    async def test_ok(self, mock_base):
        _setup_happy_nss(mock_base)
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r is not None

    async def test_no_button(self, mock_base):
        """click_first falla → NSSError."""
        mock_base['click_first'].return_value = False
        mod = NSSModule()
        with pytest.raises(NSSError, match="No se encontró el botón de envío"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")


class TestObtenerNSS:
    async def test_desde_html(self, mock_base):
        """NSS de 11 dígitos encontrado en HTML."""
        mock_base['page'].content.return_value = (
            "<html>Tu NSS es: 12345678901</html>"
        )
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r["nss"] == "12345678901"

    async def test_con_ocr(self, mock_base):
        """HTML sin NSS → OCR intenta."""
        mock_base['page'].content.return_value = "<html>Sin información</html>"

        fake_ocr = MagicMock()
        fake_ocr.extract_from_screenshot.return_value = {"nss": "98765432109"}
        mod = NSSModule(use_ocr=True)
        mod.ocr = fake_ocr
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r["nss"] == "98765432109"

    async def test_ocr_falla_y_captcha_error(self, mock_base):
        """HTML sin NSS + OCR falla + captcha error → NSSError."""
        mock_base['page'].content.return_value = (
            "<html>captcha no válido ingrese nuevamente</html>"
        )
        fake_ocr = MagicMock()
        fake_ocr.extract_from_screenshot.side_effect = ValueError("ocr fail")
        mod = NSSModule(use_ocr=True)
        mod.ocr = fake_ocr

        with pytest.raises(NSSError, match="CAPTCHA inválido"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")

    async def test_nss_por_correo(self, mock_base):
        """Éxito + html sin NSS → mail_reader.wait_for_imss_email."""
        mock_base['page'].content.return_value = (
            "<html>se ha enviado un correo</html>"
        )
        mail_reader = MagicMock()
        mail_reader.wait_for_imss_email.return_value = {"nss": "55555555555"}
        mod = NSSModule(mail_reader=mail_reader)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r["nss"] == "55555555555"

    async def test_envio_sin_mail_reader(self, mock_base):
        """Éxito + html "se ha enviado" + sin mail_reader → ENVIADO_AL_CORREO."""
        mock_base['page'].content.return_value = (
            "<html>se ha enviado un correo</html>"
        )
        mod = NSSModule(mail_reader=None)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r["nss"] == "ENVIADO_AL_CORREO"

    async def test_con_link_verificacion(self, mock_base):
        """Mail devuelve verification_link → goto + re-escaneo."""
        mock_base['page'].content.side_effect = [
            "<html>se ha enviado un correo</html>",
            "<html>Tu NSS: 77777777777</html>",
        ]
        mail_reader = MagicMock()
        mail_reader.wait_for_imss_email.return_value = {
            "verification_link": "https://imss.gob.mx/verify?token=abc",
            "nss": None,
        }
        mod = NSSModule(mail_reader=mail_reader)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r["nss"] == "77777777777"
        mock_base['page'].goto.assert_called_once()

    async def test_page_content_recuperacion(self, mock_base):
        """page.content() falla → wait_for_load_state + reintento."""
        mock_base['page'].content.side_effect = [
            Exception("broken"),
            "<html>Tu NSS: 11111111111</html>",
        ]
        mod = NSSModule()
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r["nss"] == "11111111111"

    async def test_page_content_recuperacion_falla(self, mock_base):
        """page.content() + wait_for_load_state fallan → NSSError."""
        mock_base['page'].content.side_effect = Exception("broken")
        mock_base['page'].wait_for_load_state.side_effect = Exception("no load")
        mod = NSSModule()
        with pytest.raises(NSSError, match="conexión con el portal se perdió"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")

    async def test_sin_nss_ni_correo(self, mock_base):
        """No NSS, no OCR, no correo, no números → NSSError."""
        mock_base['page'].content.return_value = "<html>Página genérica</html>"
        mod = NSSModule(use_ocr=False)
        with pytest.raises(NSSError, match="No se pudo obtener el NSS"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")

    async def test_any_11_digit_fallback(self, mock_base):
        """No NSS exacto pero hay número de 11 dígitos → usa ese."""
        mock_base['page'].content.return_value = (
            "<html>Folio: 99999999999</html>"
        )
        mod = NSSModule(use_ocr=False)
        r = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
        assert r["nss"] == "99999999999"

    async def test_mail_reader_verification_link_exception(self, mock_base):
        """goto lanza excepción → debug + continúa."""
        content1 = "<html>se ha enviado un correo</html>"
        # Primer goto (carga inicial) ok, segundo goto falla
        mock_base['page'].goto.side_effect = [mock_base['page'], ValueError("goto fail")]
        mock_base['page'].content.side_effect = [content1, Exception("fail")]

        mail_reader = MagicMock()
        mail_reader.wait_for_imss_email.return_value = {
            "verification_link": "https://imss.gob.mx/verify",
            "nss": None,
        }
        mod = NSSModule(mail_reader=mail_reader)
        with pytest.raises(NSSError, match="No se pudo obtener el NSS"):
            await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")


class TestConstants:
    def test_recaptcha_fallback_key(self):
        assert RECAPTCHA_SITE_KEY_FALLBACK.startswith("6LfFGgkTAAAA")
