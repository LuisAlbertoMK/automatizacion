"""Tests for remaining tramite modules: Antecedentes, CitaINE, CitaSAT, ControlConfianza."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import AntecedentesError, CitaINEerror, CitaSATError, ControlConfianzaError


class TestAntecedentesModule:
    MODULE = "src.modules.antecedentes"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.antecedentes import AntecedentesModule
        mod = AntecedentesModule()
        expected = {"status": "ok", "folio": "FOL123"}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com", password="pass")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_consultar_missing_curp(self):
        from src.modules.antecedentes import AntecedentesModule
        mod = AntecedentesModule()
        with pytest.raises(AntecedentesError, match="Se requieren CURP"):
            await mod.consultar(curp="", correo="")

    @pytest.mark.asyncio
    async def test_wrapped_error(self):
        """antecedentes does NOT wrap errors — RuntimeError propagates."""
        from src.modules.antecedentes import AntecedentesModule
        mod = AntecedentesModule()
        with (
            patch.object(mod, "_run", AsyncMock(side_effect=RuntimeError("fail"))),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            with pytest.raises(RuntimeError, match="fail"):
                await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")
            mock_cb.assert_awaited_once()


class TestCitaINEModule:
    MODULE = "src.modules.cita_ine"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.cita_ine import CitaINEModule
        mod = CitaINEModule()
        expected = {"cita": "2026-08-01", "curp": "GALJ...", "pdf_path": None}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_curp(self):
        from src.modules.cita_ine import CitaINEModule
        mod = CitaINEModule()
        with pytest.raises(CitaINEerror, match="Se requiere CURP para cita INE"):
            await mod.consultar(curp="")


class TestCitaSATModule:
    MODULE = "src.modules.cita_sat"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.cita_sat import CitaSATModule
        mod = CitaSATModule()
        expected = {"cita": "2026-09-01", "curp": "GALJ...", "pdf_path": None}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(rfc="RFC123456ABC", curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_rfc(self):
        from src.modules.cita_sat import CitaSATModule
        mod = CitaSATModule()
        with pytest.raises(CitaSATError, match="Se requiere RFC para cita SAT"):
            await mod.consultar(rfc="")


class TestControlConfianzaModule:
    MODULE = "src.modules.control_confianza"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.control_confianza import ControlConfianzaModule
        mod = ControlConfianzaModule()
        expected = {"status": "ok", "folio": "FOL123", "curp": "GALJ..."}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_curp(self):
        from src.modules.control_confianza import ControlConfianzaModule
        mod = ControlConfianzaModule()
        with pytest.raises(ControlConfianzaError, match="Se requiere CURP"):
            await mod.consultar(curp="")
