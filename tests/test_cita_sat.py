"""Tests para src/tramites/cita_sat.py — Cita SAT."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exceptions import CitaSATError
from src.tramites.cita_sat import CitaSATModule


class TestConsultar:
    async def test_sin_rfc(self):
        mod = CitaSATModule()
        with pytest.raises(CitaSATError, match="Se requiere RFC"):
            await mod.consultar(rfc="")

    async def test_exitoso_solo_rfc(self, mock_base):
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX")
        assert r["status"] == "cita_agendada"
        assert r["rfc"] == "BAAC800101XXX"
        assert r["pdf_path"] == "test.pdf"

    async def test_con_curp_y_email(self, mock_base):
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX", curp="ABCD123456HDFRRN08",
                                email="juan@test.com")
        assert r["status"] == "cita_agendada"

    async def test_sin_recaptcha(self, mock_base):
        mock_base['detect_site_key'].return_value = None
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX")
        mock_base['wait_for_recaptcha'].assert_not_called()

    async def test_con_recaptcha(self, mock_base):
        mock_base['detect_site_key'].return_value = "6Lc..."
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX")
        mock_base['wait_for_recaptcha'].assert_called_once()

    async def test_fecha_clickeada(self, mock_base):
        el = MagicMock()
        el.click = AsyncMock()
        mock_base['page'].query_selector = AsyncMock(return_value=el)
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX")
        el.click.assert_called()

    async def test_sin_fecha(self, mock_base):
        mock_base['page'].query_selector = AsyncMock(return_value=None)
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX")
        assert r["status"] == "cita_agendada"

    async def test_fecha_exception(self, mock_base):
        mock_base['page'].query_selector.side_effect = ValueError("")
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX")
        assert r["status"] == "cita_agendada"

    async def test_pdf_no_descargado(self, mock_base):
        mock_base['download_pdf'].return_value = None
        mod = CitaSATModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(rfc="BAAC800101XXX")
        assert r["pdf_path"] is None

    async def test_error_generico(self, mock_base):
        mock_base['goto'].side_effect = ValueError("fail")
        mod = CitaSATModule()
        with pytest.raises(CitaSATError, match="Error en cita SAT"):
            await mod.consultar(rfc="BAAC800101XXX")

    async def test_error_re_raise(self, mock_base):
        mock_base['goto'].side_effect = CitaSATError("no disponible")
        mod = CitaSATModule()
        with pytest.raises(CitaSATError, match="no disponible"):
            await mod.consultar(rfc="BAAC800101XXX")
