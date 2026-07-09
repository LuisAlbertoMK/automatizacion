"""Tests para src/tramites/rfc.py — Consulta RFC en SAT."""

import pytest

from src.exceptions import RFCError
from src.tramites.rfc import RFCModule


class TestConsultar:
    """Cubre RFCModule.consultar (líneas 28-62)."""

    async def test_sin_curp(self):
        """Line 42-43: curp vacío → RFCError."""
        mod = RFCModule()
        with pytest.raises(RFCError, match="Se requiere CURP"):
            await mod.consultar(curp="")

    async def test_exitoso_solo_curp(self, mock_base):
        """Happy path: solo CURP, RFC encontrado en HTML."""
        mock_base['page'].content.return_value = (
            "<html>RFC: BAAC800101XXX</html>"
        )
        mod = RFCModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08")

        assert result["rfc"] == "BAAC800101XXX"
        assert result["curp"] == "ABCD123456HDFRRN08"
        assert result["pdf_path"] == "test.pdf"
        mock_base['goto'].assert_called_once()

    async def test_con_datos_personales(self, mock_base):
        """Nombre + apellidos pasados → fill_field llamado para cada uno."""
        mock_base['page'].content.return_value = (
            "<html>RFC: XEXX010101000</html>"
        )
        mod = RFCModule()
        await mod.consultar(
            curp="ABCD123456HDFRRN08",
            nombre="Juan",
            apellido_paterno="Pérez",
            apellido_materno="López",
        )
        # 3 fill_field adicionales (nombre, paterno, materno)
        assert mock_base['fill_field'].call_count >= 3

    async def test_nombre_sin_apellidos(self, mock_base):
        """Solo nombre, sin apellidos."""
        mock_base['page'].content.return_value = (
            "<html>RFC: XEXX010101000</html>"
        )
        mod = RFCModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08", nombre="María")
        assert result["rfc"] == "XEXX010101000"

    async def test_solo_apellido_paterno(self, mock_base):
        """Solo apellido paterno."""
        mock_base['page'].content.return_value = (
            "<html>RFC: XEXX010101000</html>"
        )
        mod = RFCModule()
        result = await mod.consultar(
            curp="ABCD123456HDFRRN08", apellido_paterno="García"
        )
        assert result["rfc"] == "XEXX010101000"

    async def test_rfc_no_encontrado(self, mock_base):
        """HTML sin RFC → rfc = NO_ENCONTRADO + warn."""
        mock_base['page'].content.return_value = (
            "<html>No hay información disponible</html>"
        )
        mod = RFCModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08")

        assert result["rfc"] == "NO_ENCONTRADO"
        mock_base['warn'].assert_called_once()

    async def test_pdf_no_descargado(self, mock_base):
        """download_pdf devuelve None → pdf_path = None."""
        mock_base['download_pdf'].return_value = None
        mock_base['page'].content.return_value = (
            "<html>RFC: BAAC800101XXX</html>"
        )
        mod = RFCModule()
        result = await mod.consultar(curp="ABCD123456HDFRRN08")

        assert result["pdf_path"] is None

    async def test_error_generico(self, mock_base):
        """Exception genérica → RFCError wrapper."""
        mock_base['goto'].side_effect = TimeoutError("timeout")
        mod = RFCModule()
        with pytest.raises(RFCError, match="Error consultando RFC"):
            await mod.consultar(curp="ABCD123456HDFRRN08")

    async def test_rfc_error_re_raise(self, mock_base):
        """RFCError dentro de _run → re-lanzada."""
        mock_base['goto'].side_effect = RFCError("error específico")
        mod = RFCModule()
        with pytest.raises(RFCError, match="error específico"):
            await mod.consultar(curp="ABCD123456HDFRRN08")
