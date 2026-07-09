"""Tests para src/tramites/tenencia.py — Tenencia Vehicular Edomex."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import TenenciaError
from src.tramites.tenencia import TenenciaModule


@pytest.fixture(autouse=True)
def _fast_sleep():
    """Evita asyncio.sleep real en tenencia.py (tiene sleeps de 2-3s)."""
    with patch("asyncio.sleep", AsyncMock()):
        yield


@pytest.fixture
def mod():
    m = TenenciaModule()
    m.interaction = MagicMock()
    m.interaction.prompt = AsyncMock(return_value="ABC123")
    return m


class TestConsultar:
    async def test_sin_placa(self):
        mod = TenenciaModule()
        with pytest.raises(TenenciaError, match="Se requiere placa"):
            await mod.consultar(placa="")

    async def test_exitoso_sin_serie(self, mock_base, mod):
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234")
        assert r["monto"] is not None
        assert r["pdf_path"] == "test.pdf"

    async def test_exitoso_con_serie(self, mock_base, mod):
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234", numero_serie="VIN1234567890")
        assert r["monto"] is not None

    async def test_error_generico(self, mock_base):
        """"consultar no tiene try/except, el error se propaga tal cual."""
        mock_base['goto'].side_effect = ValueError("fail")
        mod = TenenciaModule()
        with pytest.raises(ValueError):
            await mod.consultar(placa="ABC1234")


class TestIngresarPlaca:
    async def test_ok(self, mock_base, mod):
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234")
        assert r is not None

    async def test_campo_no_encontrado(self, mock_base, mod):
        mock_base['fill_field'].return_value = False
        with pytest.raises(TenenciaError, match="No se encontró el campo de placa"):
            await mod.consultar(placa="ABC1234")


class TestIngresarSerie:
    async def test_ok(self, mock_base, mod):
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234", numero_serie="VIN123")
        assert r is not None

    async def test_no_encontrada_warn(self, mock_base, mod):
        _setup_happy(mock_base)
        mock_base['fill_field'].side_effect = [True, False]  # placa ok, serie not found
        r = await mod.consultar(placa="ABC1234", numero_serie="VIN123")
        assert r is not None
        mock_base['warn'].assert_called()


class TestResolverCaptcha:
    async def test_automático(self, mock_base, mod):
        """resolve_image_captcha resuelve → OK."""
        mock_base['resolve_image_captcha'].return_value = True
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234")
        assert r is not None

    async def test_sin_captcha(self, mock_base, mod):
        """resolve falla + no hay img captcha → return."""
        _setup_happy(mock_base, skip_locator=True)
        mock_base['resolve_image_captcha'].return_value = False
        mock_base['page'].locator = MagicMock(side_effect=_smart_locator(captcha_count=0))
        r = await mod.consultar(placa="ABC1234")
        assert r is not None

    async def test_manual(self, mock_base, mod):
        """resolve falla + captcha presente → prompt manual."""
        _setup_happy(mock_base, skip_locator=True)
        mock_base['resolve_image_captcha'].return_value = False
        mock_base['page'].locator = MagicMock(side_effect=_smart_locator(captcha_count=1))
        r = await mod.consultar(placa="ABC1234")
        mod.interaction.prompt.assert_called_once()


class TestEnviarConsulta:
    async def test_ok_button(self, mock_base, mod):
        """Encuentra botón submit → click."""
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234")
        assert r is not None

    async def test_no_button(self, mock_base, mod):
        """Ningún botón encontrado → TenenciaError."""
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        loc.first.is_visible = AsyncMock(return_value=False)
        mock_base['page'].locator = MagicMock(return_value=loc)
        with pytest.raises(TenenciaError, match="No se encontró el botón"):
            await mod.consultar(placa="ABC1234")

    async def test_click_exception(self, mock_base, mod):
        """click en botón lanza excepción → debug + continue."""
        good_loc = MagicMock()
        good_loc.count = AsyncMock(return_value=1)
        good_loc.first.is_visible = AsyncMock(return_value=True)
        good_loc.first.click = AsyncMock(side_effect=ValueError("click fail"))

        # Make all locator calls return the same good_loc
        mock_base['page'].locator = MagicMock(return_value=good_loc)
        _setup_happy(mock_base, skip_locator=True)
        with pytest.raises(TenenciaError, match="No se encontró el botón"):
            await mod.consultar(placa="ABC1234")


class TestExtraerInformacion:
    async def test_con_monto_y_linea(self, mock_base, mod):
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = (
            "<html>Monto: $1,500.00 línea: 12345678901234567890</html>"
        )
        r = await mod.consultar(placa="ABC1234")
        assert r["monto"] == "1,500.00"
        assert r["linea_captura"] == "12345678901234567890"

    async def test_sin_monto(self, mock_base, mod):
        _setup_happy(mock_base)
        mock_base['page'].content.return_value = "<html>Sin información</html>"
        r = await mod.consultar(placa="ABC1234")
        assert r["monto"] == "No disponible"
        assert r["linea_captura"] is None

    async def test_pdf_no_descargado(self, mock_base, mod):
        mock_base['download_pdf'].return_value = None
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234")
        assert r["pdf_path"] is None


class TestScreenshot:
    async def test_screenshot_falla(self, mock_base, mod):
        """page.screenshot falla → debug + continúa."""
        mock_base['page'].screenshot.side_effect = Exception("no screenshot")
        _setup_happy(mock_base)
        r = await mod.consultar(placa="ABC1234")
        assert r is not None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _smart_locator(*, captcha_count=0):
    """Side-effect factory: captcha selectors vs button selectors."""
    captcha_loc = MagicMock()
    captcha_loc.count = AsyncMock(return_value=captcha_count)
    button_loc = MagicMock()
    button_loc.count = AsyncMock(return_value=1)
    button_loc.first.is_visible = AsyncMock(return_value=True)
    button_loc.first.click = AsyncMock()

    def _side_effect(sel):
        if 'captcha' in str(sel).lower():
            return captcha_loc
        return button_loc

    return _side_effect


def _setup_happy(mock_base, skip_locator=False):
    """Configura mocks para flujo exitoso estándar de tenencia."""
    page = mock_base['page']

    # Default locator for _enviar_consulta and _resolver_captcha
    if not skip_locator:
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        loc.first.is_visible = AsyncMock(return_value=True)
        loc.first.click = AsyncMock()
        page.locator = MagicMock(return_value=loc)

    # Default content for extracción
    page.content.return_value = (
        "<html>Monto: $5,000.00 línea: 98765432109876543210</html>"
    )
