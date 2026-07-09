"""Tests para src/tramites/semanas.py — Consulta de semanas cotizadas IMSS."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.exceptions import SemanasError
from src.tramites.semanas import SemanasModule


class TestConsultar:
    """Cubre SemanasModule.consultar (líneas 26-55)."""

    async def test_sin_curp(self):
        """Line 51: curp vacío → SemanasError."""
        mod = SemanasModule()
        with pytest.raises(SemanasError, match="Se requiere CURP"):
            await mod.consultar(curp="")

    async def test_exitoso_con_curp(self, mock_base):
        """Happy path: solo CURP, semanas encontradas."""
        mock_base['page'].content.return_value = (
            "<html>Usted tiene 850 semanas cotizadas</html>"
        )
        mod = SemanasModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08")

        assert result["semanas"] == "850"
        assert result["curp"] == "ABCD123456HDFRRN08"
        assert result["nss"] == "CONSULTADO"
        assert result["pdf_path"] == "test.pdf"
        mock_base['goto'].assert_called_once()

    async def test_exitoso_con_nss(self, mock_base):
        """NSS presente → fill_field con NSS exitoso."""
        mock_base['fill_field'].return_value = True  # NSS field found
        mock_base['page'].content.return_value = (
            "<html>Usted tiene 1200 semanas cotizadas</html>"
        )
        mod = SemanasModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08", nss="12345678901")

        assert result["semanas"] == "1200"
        assert result["nss"] == "12345678901"
        # Debe haber llamado fill_field con NSS
        nss_call = any(
            "nss" in str(c[0][1]) for c in mock_base['fill_field'].call_args_list
        )
        assert nss_call

    async def test_nss_falla_fallback_curp(self, mock_base):
        """NSS no encontrado → warn + fallback a CURP."""
        mock_base['fill_field'].return_value = False  # NSS field NOT found
        mock_base['page'].content.return_value = (
            "<html>Usted tiene 300 semanas cotizadas</html>"
        )
        mod = SemanasModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08", nss="12345678901")

        assert result["semanas"] == "300"
        mock_base['warn'].assert_called_once()  # warn por NSS no encontrado

    async def test_sin_semanas_match(self, mock_base):
        """Content sin coincidencia → semanas_val = None."""
        mock_base['page'].content.return_value = "<html>No hay información</html>"
        mod = SemanasModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08")

        assert result["semanas"] is None

    async def test_pdf_no_descargado(self, mock_base):
        """download_pdf devuelve None → pdf_path = None."""
        mock_base['download_pdf'].return_value = None
        mock_base['page'].content.return_value = (
            "<html>Usted tiene 500 semanas cotizadas</html>"
        )
        mod = SemanasModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08")

        assert result["pdf_path"] is None
        assert result["semanas"] == "500"

    async def test_error_generico_en_run(self, mock_base):
        """Exception genérica en _run → SemanasError envuelta."""
        mock_base['goto'].side_effect = ValueError("Connection refused")
        mod = SemanasModule()
        with pytest.raises(SemanasError, match="Error consultando semanas"):
            await mod.consultar(curp="ABCD123456HDFRRN08")

    async def test_semanas_error_re_raise(self, mock_base):
        """SemanasError dentro de _run → re-lanzada sin wrapper."""
        mock_base['goto'].side_effect = SemanasError("Error interno")
        mod = SemanasModule()
        with pytest.raises(SemanasError, match="Error interno"):
            await mod.consultar(curp="ABCD123456HDFRRN08")
