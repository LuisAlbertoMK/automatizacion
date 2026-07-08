"""Tests for small tramite modules: Semanas, RFC, ActaNacimiento, Pasaporte."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import ActaNacimientoError, PasaporteError, RFCError, SemanasError


class TestSemanasModule:
    MODULE = "src.modules.semanas"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.semanas import SemanasModule
        mod = SemanasModule()
        expected = {"semanas": "500", "nss": "12345678901", "curp": "GALJ..."}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_consultar_missing_curp(self):
        from src.modules.semanas import SemanasModule
        mod = SemanasModule()
        with pytest.raises(SemanasError, match="Se requiere CURP"):
            await mod.consultar(curp="")

    @pytest.mark.asyncio
    async def test_run_error_wrapped(self):
        from src.modules.semanas import SemanasModule
        mod = SemanasModule()
        with (
            patch.object(mod, "_run", AsyncMock(side_effect=ValueError("boom"))),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            with pytest.raises(SemanasError, match="Error consultando semanas"):
                await mod.consultar(curp="GALJ800101HDFXXXX0")
            mock_cb.assert_awaited_once()


class TestRFCModule:
    MODULE = "src.modules.rfc"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.rfc import RFCModule
        mod = RFCModule()
        expected = {"rfc": "GALJ800101XXX", "curp": "GALJ...", "pdf_path": None}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_consultar_missing_curp(self):
        from src.modules.rfc import RFCModule
        mod = RFCModule()
        with pytest.raises(RFCError, match="Se requiere CURP"):
            await mod.consultar(curp="")


class TestActaNacimientoModule:
    MODULE = "src.modules.acta_nacimiento"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.acta_nacimiento import ActaNacimientoModule
        mod = ActaNacimientoModule()
        expected = {"curp": "GALJ...", "pdf_path": "/tmp/a.pdf", "status": "descargado"}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_consultar_missing_curp(self):
        from src.modules.acta_nacimiento import ActaNacimientoModule
        mod = ActaNacimientoModule()
        with pytest.raises(ActaNacimientoError, match="Se requiere CURP"):
            await mod.consultar(curp="")


class TestPasaporteModule:
    MODULE = "src.modules.pasaporte"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.pasaporte import PasaporteModule
        mod = PasaporteModule()
        expected = {"cita": "2026-07-15", "curp": "GALJ...", "pdf_path": None}
        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser"),
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0")
        assert result == expected

    @pytest.mark.asyncio
    async def test_consultar_missing_curp(self):
        from src.modules.pasaporte import PasaporteModule
        mod = PasaporteModule()
        with pytest.raises(PasaporteError, match="Se requiere CURP"):
            await mod.consultar(curp="")
