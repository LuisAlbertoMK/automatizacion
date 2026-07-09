"""Tests para src/tramites/acta_nacimiento.py — Descarga acta RENAPO."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import ActaNacimientoError
from src.tramites.acta_nacimiento import ActaNacimientoModule


class TestConsultar:
    async def test_sin_curp(self):
        mod = ActaNacimientoModule()
        with pytest.raises(ActaNacimientoError, match="Se requiere CURP"):
            await mod.consultar(curp="")

    async def test_exitoso(self, mock_base):
        mod = ActaNacimientoModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "descargado"
        assert r["curp"] == "ABCD123456HDFRRN08"
        assert r["pdf_path"] == "test.pdf"

    async def test_fallback_download(self, mock_base):
        """download_pdf falla → fallback: query_selector + requests."""
        mock_base['download_pdf'].return_value = None
        # Mock page.query_selector para el PDF alternativo
        link = MagicMock()
        link.get_attribute = AsyncMock(return_value="/actas/abc.pdf")
        mock_base['page'].query_selector = AsyncMock(return_value=link)

        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.content = b"%PDF-1.4..."

            mod = ActaNacimientoModule()
            r = await mod.consultar(curp="ABCD123456HDFRRN08")

        assert r["status"] == "descargado"
        assert r["pdf_path"] is not None
        assert ".pdf" in r["pdf_path"]

    async def test_pdf_no_descargado(self, mock_base):
        """Sin PDF primario ni fallback → status pendiente."""
        mock_base['download_pdf'].return_value = None
        mock_base['page'].query_selector = AsyncMock(return_value=None)
        mod = ActaNacimientoModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "pendiente"
        assert r["pdf_path"] is None

    async def test_fallback_link_sin_href(self, mock_base):
        """Query selector encuentra link pero sin href → skip."""
        mock_base['download_pdf'].return_value = None
        link = MagicMock()
        link.get_attribute = AsyncMock(return_value=None)
        mock_base['page'].query_selector = AsyncMock(return_value=link)
        mod = ActaNacimientoModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "pendiente"

    async def test_fallback_http_falla(self, mock_base):
        """Fallback: requests.get devuelve != 200 → skip."""
        mock_base['download_pdf'].return_value = None
        link = MagicMock()
        link.get_attribute = AsyncMock(return_value="/actas/abc.pdf")
        mock_base['page'].query_selector = AsyncMock(return_value=link)

        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 500
            mod = ActaNacimientoModule()
            r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "pendiente"

    async def test_fallback_exception(self, mock_base):
        """Fallback lanza excepción → catch, status pendiente."""
        mock_base['download_pdf'].return_value = None
        link = MagicMock()
        link.get_attribute = AsyncMock(side_effect=ValueError("fail"))
        mock_base['page'].query_selector = AsyncMock(return_value=link)
        mod = ActaNacimientoModule()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "pendiente"

    async def test_error_generico(self, mock_base):
        mock_base['goto'].side_effect = ValueError("fail")
        mod = ActaNacimientoModule()
        with pytest.raises(ActaNacimientoError, match="Error consultando acta"):
            await mod.consultar(curp="ABCD123456HDFRRN08")

    async def test_error_re_raise(self, mock_base):
        mock_base['goto'].side_effect = ActaNacimientoError("no disponible")
        mod = ActaNacimientoModule()
        with pytest.raises(ActaNacimientoError, match="no disponible"):
            await mod.consultar(curp="ABCD123456HDFRRN08")
