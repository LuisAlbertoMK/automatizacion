"""Tests for CURPModule, NSSModule, TenenciaModule (critical path)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import CURPError, NSSError, TenenciaError


class TestCURPModule:
    MODULE = "src.modules.curp"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.curp import CURPModule
        mod = CURPModule()
        expected = {"curp": "GALJ800101HDFXXXX0", "pdf_path": "/tmp/c.pdf"}

        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)) as mock_run,
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0")

        assert result == expected
        mock_run.assert_awaited_once()
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_consultar_missing_curp(self):
        from src.modules.curp import CURPModule
        mod = CURPModule()
        with pytest.raises(CURPError, match="Se requiere curp"):
            await mod.consultar(curp="")

    @pytest.mark.asyncio
    async def test_consultar_browser_error(self):
        """CURP does NOT wrap errors — launch_browser errors propagate."""
        from src.modules.curp import CURPModule
        mod = CURPModule()
        with (
            patch.object(mod, "launch_browser", AsyncMock(side_effect=TimeoutError("timeout"))),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            with pytest.raises(TimeoutError, match="timeout"):
                await mod.consultar(curp="GALJ800101HDFXXXX0")
            mock_cb.assert_not_called()  # never got past launch_browser

    @pytest.mark.asyncio
    async def test_consultar_run_error_re_raised(self):
        from src.modules.curp import CURPModule
        mod = CURPModule()
        with (
            patch.object(mod, "_run", AsyncMock(side_effect=CURPError("custom"))),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            with pytest.raises(CURPError, match="custom"):
                await mod.consultar(curp="GALJ800101HDFXXXX0")
            mock_cb.assert_awaited_once()


class TestNSSModule:
    MODULE = "src.modules.nss"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.nss import NSSModule
        mod = NSSModule()
        expected = {"nss": "12345678901"}

        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(curp="GALJ800101HDFXXXX0", correo="a@b.com")

        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_consultar_missing_curp(self):
        from src.modules.nss import NSSModule
        mod = NSSModule()
        with pytest.raises(NSSError, match="Se requieren CURP y correo"):
            await mod.consultar(curp="", correo="a@b.com")


class TestTenenciaModule:
    MODULE = "src.modules.tenencia"

    @pytest.mark.asyncio
    async def test_consultar_success(self):
        from src.modules.tenencia import TenenciaModule
        mod = TenenciaModule()
        expected = {"status": "ok", "adeudo": 1500.0}

        with (
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mod.launch_browser = AsyncMock(return_value=MagicMock(page=MagicMock(), browser=MagicMock()))
            result = await mod.consultar(placa="ABC123")

        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_consultar_missing_placa(self):
        from src.modules.tenencia import TenenciaModule
        mod = TenenciaModule()
        with pytest.raises(TenenciaError, match="Se requiere placa"):
            await mod.consultar(placa="")
