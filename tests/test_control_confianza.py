"""Tests para src/tramites/control_confianza.py — Control de Confianza SESNSP."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.exceptions import ControlConfianzaError
from src.tramites.control_confianza import ControlConfianzaModule


class TestConsultar:
    async def test_sin_curp(self):
        mod = ControlConfianzaModule()
        with pytest.raises(ControlConfianzaError, match="Se requiere CURP"):
            await mod.consultar(curp="")

    async def test_exitoso_minimo(self, mock_base):
        """Solo CURP, sin campos opcionales."""
        mod = ControlConfianzaModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "completado"
        assert r["curp"] == "ABCD123456HDFRRN08"
        assert r["pdf_path"] == "test.pdf"

    async def test_con_todos_los_datos(self, mock_base):
        """Todos los campos opcionales presentes."""
        mod = ControlConfianzaModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(
            curp="ABCD123456HDFRRN08",
            rfc="BAAC800101XXX",
            nombre="Juan Pérez",
            fecha_nacimiento="01/01/1990",
            estado_nacimiento="CDMX",
            domicilio="Calle 123",
            telefono="5512345678",
            email="juan@test.com",
            estado_civil="casado",
            escolaridad="maestria",
            ingreso_mensual=50000,
            egreso_mensual=30000,
        )
        assert r["status"] == "completado"
        # Debe haber llamado fill_field para cada campo presente
        assert mock_base['fill_field'].call_count >= 9

    async def test_select_loop(self, mock_base):
        """selectores de estado civil/escolaridad: locator.count > 0 → select_option."""
        loc = MagicMock()
        loc.count = AsyncMock(return_value=1)
        mock_base['page'].locator = MagicMock(return_value=loc)
        mod = ControlConfianzaModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        mock_base['page'].select_option.assert_called()

    async def test_select_loop_exception(self, mock_base):
        """select loop inner except: locator.count falla → debug + continúa."""
        loc = MagicMock()
        loc.count = AsyncMock(side_effect=[Exception("fail"), 1])
        mock_base['page'].locator = MagicMock(return_value=loc)
        mod = ControlConfianzaModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["status"] == "completado"

    async def test_pdf_no_descargado(self, mock_base):
        mock_base['download_pdf'].return_value = None
        mod = ControlConfianzaModule()
        mod.interaction = MagicMock()
        mod.interaction.prompt_enter = AsyncMock()
        r = await mod.consultar(curp="ABCD123456HDFRRN08")
        assert r["pdf_path"] is None

    async def test_error_generico(self, mock_base):
        mock_base['goto'].side_effect = ValueError("fail")
        mod = ControlConfianzaModule()
        with pytest.raises(ControlConfianzaError, match="Error en Control de Confianza"):
            await mod.consultar(curp="ABCD123456HDFRRN08")

    async def test_error_re_raise(self, mock_base):
        mock_base['goto'].side_effect = ControlConfianzaError("no disponible")
        mod = ControlConfianzaModule()
        with pytest.raises(ControlConfianzaError, match="no disponible"):
            await mod.consultar(curp="ABCD123456HDFRRN08")
