"""Tests para src/tramites/credito.py — Reportes de Crédito (Buró / Círculo)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import BuroError, CirculoError, ModuleError

# ── Helpers ──────────────────────────────────────────────────────────────────

_OUTPUT_DIR = Path("./output")


def _mock_page():
    """Crea un mock de playwright.async_api.Page — helper, no fixture."""
    page = MagicMock()
    page.pdf = AsyncMock(return_value=b"")
    return page


def _make_credito(tipo="buro"):
    """Crea un CreditoModule con `browser_context` mockeado."""
    from src.tramites.credito import CreditoModule

    module = CreditoModule(tipo=tipo, use_ocr=False)
    # Reemplazar métodos pesados por mocks
    module.log = MagicMock()
    module.debug = MagicMock()
    module.error = MagicMock()
    module.goto = AsyncMock()
    module.fill_field = AsyncMock(return_value=True)
    module.interaction = MagicMock()
    module.interaction.prompt_enter = AsyncMock()
    module.download_pdf = AsyncMock(return_value=None)
    return module


def _mock_browser_context(module, page):
    """Parchea `browser_context` para que devuelva un mock sin browser real."""
    mock_br = AsyncMock()
    mock_br.page = page
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_br
    mock_ctx.__aexit__.return_value = None
    return patch.object(module, "browser_context", return_value=mock_ctx)


# ── CreditoModule.__init__ ──────────────────────────────────────────────────

class TestInit:
    def test_tipo_invalido(self):
        with pytest.raises(ModuleError, match="Tipo de cr.*dito inv.*lido"):
            from src.tramites.credito import CreditoModule
            CreditoModule(tipo="invalido")

    def test_tipo_buro(self):
        from src.tramites.credito import CreditoModule
        m = CreditoModule(tipo="buro", use_ocr=False)
        assert m._cfg["name"] == "Buro"

    def test_tipo_circulo(self):
        from src.tramites.credito import CreditoModule
        m = CreditoModule(tipo="circulo", use_ocr=False)
        assert m._cfg["name"] == "Circulo"


# ── CreditoModule.consultar ─────────────────────────────────────────────────

class TestConsultar:
    """Cubre consultar() — try/except/raise (lines 112-134)."""

    @pytest.mark.asyncio
    async def test_sin_rfc(self):
        """Line 113-114: rfc vacío → ErrorCls."""
        from src.tramites.credito import CreditoModule
        m = CreditoModule(tipo="buro", use_ocr=False)
        with pytest.raises(BuroError, match="Se requiere RFC"):
            await m.consultar(rfc="", curp="CURP")

    @pytest.mark.asyncio
    async def test_flujo_exitoso(self):
        """Lines 116-128: browser_context + _run + log + return."""
        m = _make_credito("buro")
        m._run = AsyncMock(return_value={"status": "descargado"})

        with _mock_browser_context(m, page=MagicMock()) as mock_bc:
            result = await m.consultar(rfc="RFC", curp="CURP")

        assert result == {"status": "descargado"}
        mock_bc.assert_called_once()
        m.log.assert_any_call(m._cfg["msgs"]["start"])
        # Verificar que se logueó el mensaje de completado (sin approx que rompe format)
        done_calls = [c for c in m.log.call_args_list
                      if m._cfg["msgs"]["done"].split("{")[0] in str(c)]
        assert len(done_calls) == 1

    @pytest.mark.asyncio
    async def test_errorcls_re_raise(self):
        """Line 129-130: ErrorCls se re-lanza sin cambiar."""
        m = _make_credito("buro")
        m._run = AsyncMock(side_effect=BuroError("falló"))

        with _mock_browser_context(m, page=MagicMock()):
            with pytest.raises(BuroError, match="falló"):
                await m.consultar(rfc="RFC", curp="CURP")
        m.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_otro_error_se_envuelve(self):
        """Line 131-134: Exception genérico → envuelto en ErrorCls."""
        m = _make_credito("buro")
        m._run = AsyncMock(side_effect=ValueError("algo raro"))

        with _mock_browser_context(m, page=MagicMock()):
            with pytest.raises(BuroError, match="Error consultando"):
                await m.consultar(rfc="RFC", curp="CURP")
        m.error.assert_called_once()


# ── CreditoModule._run (flujo real) ─────────────────────────────────────────

class TestRun:
    """Cubre _run() — llenado de formularios, descarga, fallback (lines 140-185)."""

    @pytest.mark.asyncio
    async def test_todos_los_campos(self):
        """Lines 145-157: todos los campos opcionales se llenan."""
        m = _make_credito("buro")
        page = _mock_page()

        with _mock_browser_context(m, page):
            result = await m._run(
                page, rfc="RFC01", curp="CURP123456HDF",
                nombre="JUAN", apellido_paterno="PEREZ",
                apellido_materno="GARCIA", fecha_nacimiento="01/01/1990",
            )

        m.goto.assert_awaited_once()
        assert m.fill_field.call_count == 6
        m.interaction.prompt_enter.assert_awaited_once()
        m.download_pdf.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_solo_rfc_curp(self):
        """Lines 148-157: campos opcionales omitidos → no se llenan."""
        m = _make_credito("buro")
        page = _mock_page()

        with _mock_browser_context(m, page):
            result = await m._run(page, rfc="RFC01", curp="CURP123456HDF")

        assert m.fill_field.call_count == 2  # solo rfc + curp

    @pytest.mark.asyncio
    async def test_descarga_exitosa(self):
        """Line 164-169: download_pdf retorna Path → status 'descargado'."""
        m = _make_credito("buro")
        m.download_pdf = AsyncMock(return_value=_OUTPUT_DIR / "Buro_RFC01.pdf")
        page = _mock_page()

        with _mock_browser_context(m, page):
            result = await m._run(page, rfc="RFC01", curp="CURP123456HDF")

        assert result["status"] == "descargado"
        assert result["pdf_path"] is not None

    @pytest.mark.asyncio
    async def test_fallback_pdf(self):
        """Lines 172-176: download falla → page.pdf() como fallback."""
        m = _make_credito("buro")
        m.download_pdf = AsyncMock(return_value=None)
        page = _mock_page()
        page.pdf = AsyncMock(return_value=b"")

        with _mock_browser_context(m, page):
            result = await m._run(page, rfc="RFC01", curp="CURP123456HDF")

        page.pdf.assert_awaited_once()
        assert result["status"] == "descargado"

    @pytest.mark.asyncio
    async def test_fallback_pdf_error(self):
        """Lines 177-178: fallback también falla → status 'pendiente' (bugfix: pdf_path se resetea)."""
        m = _make_credito("buro")
        m.download_pdf = AsyncMock(return_value=None)
        page = _mock_page()
        page.pdf = AsyncMock(side_effect=Exception("PDF error"))

        with _mock_browser_context(m, page):
            result = await m._run(page, rfc="RFC01", curp="CURP123456HDF")

        assert result["status"] == "pendiente"
        assert result["pdf_path"] is None
        m.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_circulo_config(self):
        """Verifica que _run use el config correcto para círculo."""
        m = _make_credito("circulo")
        page = _mock_page()

        with _mock_browser_context(m, page):
            result = await m._run(page, rfc="RFC01", curp="CURP123456HDF")

        # El mensaje de portal usa "Círculo"
        assert any("Círculo" in str(c) for c in m.log.call_args_list)
        assert result["rfc"] == "RFC01"
