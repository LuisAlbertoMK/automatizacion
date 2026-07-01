"""Tests for CreditoModule (unified Buro/Circulo)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exceptions import BuroError, CirculoError, ModuleError


class TestCreditoModule:
    MODULE = "modules.credito"

    @pytest.mark.asyncio
    async def test_buro_consultar_success(self):
        from modules.credito import CreditoModule
        mod = CreditoModule(tipo="buro")
        expected = {"status": "descargado", "rfc": "RFC123", "curp": "GALJ...", "pdf_path": "/tmp/b.pdf"}
        with (
            patch(f"{self.MODULE}.BaseModule.launch_browser") as mock_lb,
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mock_lb.return_value = (MagicMock(), MagicMock(), MagicMock())
            result = await mod.consultar(rfc="RFC123", curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_circulo_consultar_success(self):
        from modules.credito import CreditoModule
        mod = CreditoModule(tipo="circulo")
        expected = {"status": "descargado", "rfc": "RFC123", "curp": "GALJ...", "pdf_path": "/tmp/c.pdf"}
        with (
            patch(f"{self.MODULE}.BaseModule.launch_browser") as mock_lb,
            patch.object(mod, "_run", AsyncMock(return_value=expected)),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mock_lb.return_value = (MagicMock(), MagicMock(), MagicMock())
            result = await mod.consultar(rfc="RFC123", curp="GALJ800101HDFXXXX0")
        assert result == expected
        mock_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_buro_missing_rfc(self):
        from modules.credito import CreditoModule
        mod = CreditoModule(tipo="buro")
        with pytest.raises(BuroError, match="Se requiere RFC"):
            await mod.consultar(rfc="", curp="GALJ800101HDFXXXX0")

    @pytest.mark.asyncio
    async def test_circulo_missing_rfc(self):
        from modules.credito import CreditoModule
        mod = CreditoModule(tipo="circulo")
        with pytest.raises(CirculoError, match="Se requiere RFC"):
            await mod.consultar(rfc="", curp="GALJ800101HDFXXXX0")

    @pytest.mark.asyncio
    async def test_invalid_tipo(self):
        with pytest.raises(ModuleError, match="inválido"):
            from modules.credito import CreditoModule
            CreditoModule(tipo="fake")

    @pytest.mark.asyncio
    async def test_wrapped_error(self):
        from modules.credito import CreditoModule
        mod = CreditoModule(tipo="buro")
        with (
            patch(f"{self.MODULE}.BaseModule.launch_browser") as mock_lb,
            patch.object(mod, "_run", AsyncMock(side_effect=RuntimeError("boom"))),
            patch(f"{self.MODULE}.BaseModule.close_browser") as mock_cb,
        ):
            mock_lb.return_value = (MagicMock(), MagicMock(), MagicMock())
            with pytest.raises(BuroError, match="Error consultando Buró"):
                await mod.consultar(rfc="RFC123", curp="GALJ800101HDFXXXX0")
            mock_cb.assert_awaited_once()

    # ── Backward compat: BuroModule / CirculoModule wrappers ─────────────

    @pytest.mark.asyncio
    async def test_buro_wrapper(self):
        from modules.buro import BuroModule
        mod = BuroModule()
        assert mod._cfg["name"] == "Buro"

    @pytest.mark.asyncio
    async def test_circulo_wrapper(self):
        from modules.circulo import CirculoModule
        mod = CirculoModule()
        assert mod._cfg["name"] == "Circulo"
