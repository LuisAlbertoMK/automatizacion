"""Tests para src/tramites/pasaporte.py — Cita pasaporte SRE."""

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.exceptions import PasaporteError
from src.tramites.pasaporte import PasaporteModule


def _fake_el(**kwargs):
    """Crea un mock de Playwright ElementHandle."""
    el = MagicMock()
    el.click = AsyncMock()
    el.evaluate = AsyncMock(return_value="button")
    el.query_selector_all = AsyncMock(return_value=[])
    el.select_option = AsyncMock()  # awaitable
    for k, v in kwargs.items():
        setattr(el, k, v)
    return el


def _setup_happy(mock_base):
    """Configura mocks para flujo exitoso completo."""
    page = mock_base['page']

    # Estado: page.locator(sel) → mock con .count() async
    loc = MagicMock()
    loc.count = AsyncMock(return_value=1)
    page.locator = MagicMock(return_value=loc)
    page.wait_for_selector = AsyncMock()

    # query_selector retorna elemento simulado (fecha + horario)
    page.query_selector = AsyncMock(return_value=_fake_el())


class TestConsultar:
    """Cubre PasaporteModule.consultar (líneas 25-64)."""

    async def test_sin_curp(self):
        mod = PasaporteModule()
        with pytest.raises(PasaporteError, match="Se requiere CURP"):
            await mod.consultar(curp="")

    async def test_exitoso(self, mock_base):
        _setup_happy(mock_base)
        mod = PasaporteModule()
        r = await mod.consultar(
            curp="ABCD123456HDFRRN08",
            nombre="Juan", apellido_paterno="Pérez",
            apellido_materno="López", estado="CDMX",
            telefono="5512345678", email="juan@test.com",
        )
        assert r["status"] == "cita_agendada"
        assert r["curp"] == "ABCD123456HDFRRN08"
        assert r["pdf_path"] == "test.pdf"

    async def test_estado_no_encontrado(self, mock_base):
        """wait_for_selector falla → debug + skip estado (lines 99-100)."""
        _setup_happy(mock_base)
        mock_base['page'].wait_for_selector.side_effect = TimeoutError()
        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"

    async def test_locator_estado_falla(self, mock_base):
        """page.locator().count() falla → inner except (lines 96-98), continúa."""
        _setup_happy(mock_base)
        loc = MagicMock()
        loc.count = AsyncMock(side_effect=[Exception("fail"), 1])
        mock_base['page'].locator = MagicMock(return_value=loc)
        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"

    async def test_sin_fecha_disponible(self, mock_base):
        """query_selector no encuentra fecha → skip."""
        _setup_happy(mock_base)
        mock_base['page'].query_selector = AsyncMock(return_value=None)
        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"

    async def test_fecha_clickeada(self, mock_base):
        """Slot disponible → click en la fecha."""
        el = _fake_el()
        _setup_happy(mock_base)
        mock_base['page'].query_selector = AsyncMock(return_value=el)
        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"
        el.click.assert_called()

    async def test_horario_select(self, mock_base):
        """Horario <select> → select_option(index=1)."""
        el = _fake_el()
        el.evaluate.return_value = "select"
        opts = [_fake_el(), _fake_el(), _fake_el()]
        el.query_selector_all.return_value = opts

        _setup_happy(mock_base)
        mock_base['page'].query_selector = AsyncMock(return_value=el)

        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"
        el.select_option.assert_called_once_with(index=1)

    async def test_horario_boton(self, mock_base):
        """Horario botón → click."""
        el = _fake_el()
        el.evaluate.return_value = "button"

        _setup_happy(mock_base)
        mock_base['page'].query_selector = AsyncMock(return_value=el)

        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"
        el.click.assert_called()

    async def test_horario_seleccion_falla(self, mock_base):
        """Error en click de horario → debug + continúa."""
        el = _fake_el(click=AsyncMock(side_effect=ValueError("no click")))
        _setup_happy(mock_base)
        mock_base['page'].query_selector = AsyncMock(return_value=el)

        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"

    async def test_con_recaptcha(self, mock_base):
        mock_base['detect_site_key'].return_value = "6Lc_xxx"
        _setup_happy(mock_base)
        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_sin_recaptcha(self, mock_base):
        mock_base['detect_site_key'].return_value = None
        _setup_happy(mock_base)
        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        mock_base['wait_for_recaptcha'].assert_not_called()

    async def test_pdf_no_descargado(self, mock_base):
        mock_base['download_pdf'].return_value = None
        _setup_happy(mock_base)
        mod = PasaporteModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["pdf_path"] is None

    async def test_error_generico(self, mock_base):
        mock_base['goto'].side_effect = ValueError("fail")
        mod = PasaporteModule()
        with pytest.raises(PasaporteError, match="Error en cita pasaporte"):
            await mod.consultar(curp="ABCD123456HDFRRN08")

    async def test_error_re_raise(self, mock_base):
        mock_base['goto'].side_effect = PasaporteError("no disponible")
        mod = PasaporteModule()
        with pytest.raises(PasaporteError, match="no disponible"):
            await mod.consultar(curp="ABCD123456HDFRRN08")
