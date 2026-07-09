"""Tests para src/tramites/cita_ine.py — Cita INE."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from src.exceptions import CitaINEerror
from src.tramites.cita_ine import CitaINEModule


class TestConsultar:
    async def test_sin_curp(self):
        mod = CitaINEModule()
        with pytest.raises(CitaINEerror, match="Se requiere CURP"):
            await mod.consultar(curp="")

    async def test_exitoso(self, mock_base):
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"
        assert r["curp"] == "ABCD123456HDFRRN08"
        assert r["pdf_path"] == "test.pdf"

    async def test_con_nombre(self, mock_base):
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08", nombre="María")
        assert r["status"] == "cita_agendada"

    async def test_sin_recaptcha(self, mock_base):
        mock_base['detect_site_key'].return_value = None
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        mock_base['wait_for_recaptcha'].assert_not_called()

    async def test_con_recaptcha(self, mock_base):
        mock_base['detect_site_key'].return_value = "6Lc..."
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_fecha_clickeada(self, mock_base):
        el = MagicMock()
        el.click = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(return_value=el)
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        el.click.assert_called()

    async def test_sin_fecha(self, mock_base):
        mock_base['page'].query_selector = AsyncMock(return_value=None)
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"

    async def test_fecha_exception(self, mock_base):
        mock_base['page'].query_selector.side_effect = ValueError("no query")
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "cita_agendada"

    async def test_pdf_no_descargado(self, mock_base):
        mock_base['download_pdf'].return_value = None
        mod = CitaINEModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["pdf_path"] is None

    async def test_error_generico(self, mock_base):
        mock_base['goto'].side_effect = ValueError("fail")
        mod = CitaINEModule()
        with pytest.raises(CitaINEerror, match="Error en cita INE"):
            await mod.consultar(curp="ABCD123456HDFRRN08")

    async def test_error_re_raise(self, mock_base):
        mock_base['goto'].side_effect = CitaINEerror("no disponible")
        mod = CitaINEModule()
        with pytest.raises(CitaINEerror, match="no disponible"):
            await mod.consultar(curp="ABCD123456HDFRRN08")
