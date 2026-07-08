"""Tests para modules/orchestrator.py — orquestador de trámites."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.orchestrator import TRAMITES_REGISTRADOS, listar_tramites  # noqa: E402

TRAMITES_ESPERADOS = [
    "curp", "nss", "antecedentes", "tenencia",
    "rfc", "acta_nacimiento", "pasaporte", "semanas",
    "control_confianza", "buro", "circulo", "cita_ine", "cita_sat",
]

# ── Mock Module Helper ────────────────────────────────────────────────────────

def _make_mock_module():
    mod = MagicMock()
    mod.consultar = AsyncMock(return_value={"status": "ok"})
    return mod


# ── Fixtures con módulos mockeados ────────────────────────────────────────────

@pytest.fixture
def mock_multimodal():
    mm = MagicMock()
    mm.get_curp = MagicMock(return_value="CURP_MOCK")
    mm.get_email = MagicMock(return_value="mock@test.com")
    mm.get_placa = MagicMock(return_value="ABC123")
    mm.voice = True
    mm.ocr = True
    return mm


@pytest.fixture
def _mock_modules():
    """Pre-poblado del cache lazy con módulos mockeados."""
    return {t: _make_mock_module() for t in TRAMITES_ESPERADOS}


@pytest.fixture
def orchestrator(_mock_modules):
    """Crea TramitesOrchestrator con todos los módulos mockeados."""
    from src.modules.orchestrator import TramitesOrchestrator
    with patch("src.modules.orchestrator.MULTIMODAL_AVAILABLE", False):
        orch = TramitesOrchestrator()
    orch._modules = _mock_modules
    return orch


@pytest.fixture
def orchestrator_multimodal(mock_multimodal, _mock_modules):
    """TramitesOrchestrator con entrada multimodal."""
    from src.modules.orchestrator import TramitesOrchestrator
    with patch("src.modules.orchestrator.MultimodalInput", return_value=mock_multimodal):
        orch = TramitesOrchestrator()
    orch._modules = _mock_modules
    return orch


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestListarTramites:
    def test_listar_returns_all(self):
        tramites = listar_tramites()
        for t in TRAMITES_ESPERADOS:
            assert t in tramites, f"Falta trámite: {t}"
        assert len(tramites) == len(TRAMITES_ESPERADOS)

    def test_registrados_unchanged(self):
        """listar_tramites devuelve copia, no muta el original."""
        original_len = len(TRAMITES_REGISTRADOS)
        tramites = listar_tramites()
        tramites["fake_test"] = {"modulo": None, "estado": "test", "tiempo": "0s"}
        assert "fake_test" not in TRAMITES_REGISTRADOS
        assert len(TRAMITES_REGISTRADOS) == original_len

    def test_estructura_tramite(self):
        tramites = listar_tramites()
        for nombre, info in tramites.items():
            assert "modulo" in info
            assert "estado" in info
            assert "tiempo" in info

    def test_curp_estado_produccion(self):
        assert TRAMITES_REGISTRADOS["curp"]["estado"] == "✅ Producción"

    def test_nss_estado_produccion(self):
        assert TRAMITES_REGISTRADOS["nss"]["estado"] == "✅ Producción"

    def test_migrados_tienen_modulo(self):
        """Trámites migrados deben tener módulo asignado."""
        for nombre in ["rfc", "acta_nacimiento", "pasaporte", "semanas",
                        "control_confianza", "buro", "circulo", "cita_ine", "cita_sat"]:
            assert TRAMITES_REGISTRADOS[nombre]["modulo"] is not None, f"{nombre} debería tener módulo"


class TestTramitesOrchestratorInit:
    """Lines 52-82: __init__ con y sin multimodal."""

    def test_init_sets_modules(self, orchestrator):
        assert "curp" in orchestrator._modules
        assert "nss" in orchestrator._modules
        assert "antecedentes" in orchestrator._modules
        assert "tenencia" in orchestrator._modules
        assert "rfc" in orchestrator._modules
        assert "acta_nacimiento" in orchestrator._modules
        assert "pasaporte" in orchestrator._modules
        assert "semanas" in orchestrator._modules
        assert "buro" in orchestrator._modules
        assert "circulo" in orchestrator._modules

    def test_init_multimodal_not_available(self, orchestrator):
        assert orchestrator.multimodal is None

    def test_init_multimodal_available(self, orchestrator_multimodal):
        assert orchestrator_multimodal.multimodal is not None


class TestEjecutarTramite:
    """Lines 84-116: dispatch a métodos internos."""

    @pytest.mark.asyncio
    async def test_ejecutar_curp(self, orchestrator):
        with patch("builtins.input", return_value="CURP123456HDF"):
            result = await orchestrator.ejecutar_tramite("curp")
        assert result == {"status": "ok"}
        orchestrator._modules["curp"].consultar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ejecutar_nss(self, orchestrator):
        with patch("builtins.input", side_effect=["CURP123456HDF", "test@test.com"]):
            result = await orchestrator.ejecutar_tramite("nss")
        assert result == {"status": "ok"}
        orchestrator._modules["nss"].consultar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ejecutar_antecedentes(self, orchestrator):
        with patch("builtins.input", side_effect=["CURP123456HDF", "test@test.com", "n"]):
            result = await orchestrator.ejecutar_tramite("antecedentes")
        assert result == {"status": "ok"}
        orchestrator._modules["antecedentes"].consultar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ejecutar_tenencia(self, orchestrator):
        with patch("builtins.input", side_effect=["ABC123", "n"]):
            result = await orchestrator.ejecutar_tramite("tenencia")
        assert result == {"status": "ok"}
        orchestrator._modules["tenencia"].consultar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ejecutar_ambos(self, orchestrator):
        with patch("builtins.input", side_effect=["CURP123456HDF", "test@test.com"]):
            result = await orchestrator.ejecutar_tramite("ambos")
        assert "curp" in result
        assert "nss" in result

    @pytest.mark.asyncio
    async def test_ejecutar_invalido(self, orchestrator):
        with pytest.raises(ValueError, match="no soportado"):
            await orchestrator.ejecutar_tramite("invalido")


class TestEjecutarCurp:
    """Lines 118-125: _ejecutar_curp con y sin multimodal."""

    @pytest.mark.asyncio
    async def test_sin_multimodal(self, orchestrator):
        with patch("builtins.input", return_value="CURP123456HDF"):
            result = await orchestrator._ejecutar_curp("text")
        assert result == {"status": "ok"}
        orchestrator._modules["curp"].consultar.assert_awaited_once_with(curp="CURP123456HDF")

    @pytest.mark.asyncio
    async def test_con_multimodal(self, orchestrator_multimodal):
        result = await orchestrator_multimodal._ejecutar_curp("text")
        assert result == {"status": "ok"}
        orchestrator_multimodal.multimodal.get_curp.assert_called_once_with(mode="text")


class TestEjecutarNss:
    """Lines 127-136: _ejecutar_nss con y sin multimodal."""

    @pytest.mark.asyncio
    async def test_sin_multimodal(self, orchestrator):
        inputs = ["CURP123456HDF", "test@test.com"]
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator._ejecutar_nss("text")
        assert result == {"status": "ok"}
        orchestrator._modules["nss"].consultar.assert_awaited_once_with(curp="CURP123456HDF", correo="test@test.com")

    @pytest.mark.asyncio
    async def test_con_multimodal(self, orchestrator_multimodal):
        result = await orchestrator_multimodal._ejecutar_nss("text")
        assert result == {"status": "ok"}
        orchestrator_multimodal.multimodal.get_curp.assert_called_once()
        orchestrator_multimodal.multimodal.get_email.assert_called_once()


class TestEjecutarAmbos:
    """Lines 179-212: _ejecutar_ambos ejecuta CURP + NSS."""

    @pytest.mark.asyncio
    async def test_ambos_sin_multimodal(self, orchestrator):
        inputs = ["CURP123456HDF", "test@test.com"]
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator._ejecutar_ambos("text")
        assert "curp" in result
        assert "nss" in result
        orchestrator._modules["curp"].consultar.assert_awaited_once()
        orchestrator._modules["nss"].consultar.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ambos_con_multimodal(self, orchestrator_multimodal):
        result = await orchestrator_multimodal._ejecutar_ambos("text")
        assert "curp" in result
        assert "nss" in result
        orchestrator_multimodal.multimodal.get_curp.assert_called_once()
        orchestrator_multimodal.multimodal.get_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_ambos_con_pdf_path(self, orchestrator):
        """Line 209: print PDF path cuando existe."""
        from unittest.mock import AsyncMock

        orchestrator._modules["curp"].consultar = AsyncMock(
            return_value={"curp": "CURP123", "pdf_path": "/tmp/curp.pdf"}
        )
        orchestrator._modules["nss"].consultar = AsyncMock(
            return_value={"nss": "12345678901"}
        )
        with patch("builtins.input", side_effect=["CURP123", "test@test.com"]):
            result = await orchestrator._ejecutar_ambos("text")
        assert result["curp"]["curp"] == "CURP123"
        assert result["curp"]["pdf_path"] == "/tmp/curp.pdf"


class TestEjecutarAntecedentes:
    """Lines 138-158: _ejecutar_antecedentes con cuenta/no cuenta."""

    @pytest.mark.asyncio
    async def test_sin_cuenta(self, orchestrator):
        inputs = ["CURP123456HDF", "test@test.com", "n"]
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator._ejecutar_antecedentes("text")
        assert result == {"status": "ok"}
        orchestrator._modules["antecedentes"].consultar.assert_awaited_once_with(
            curp="CURP123456HDF", correo="test@test.com", password=None
        )

    @pytest.mark.asyncio
    async def test_con_cuenta(self, orchestrator):
        inputs = ["CURP123456HDF", "test@test.com", "s", "mypassword"]
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator._ejecutar_antecedentes("text")
        assert result == {"status": "ok"}
        orchestrator._modules["antecedentes"].consultar.assert_awaited_once_with(
            curp="CURP123456HDF", correo="test@test.com", password="mypassword"
        )

    @pytest.mark.asyncio
    async def test_con_multimodal(self, orchestrator_multimodal):
        """Line 141-142: _ejecutar_antecedentes con multimodal."""
        with patch("builtins.input", return_value="n"):
            result = await orchestrator_multimodal._ejecutar_antecedentes("text")
        assert result == {"status": "ok"}
        orchestrator_multimodal.multimodal.get_curp.assert_called_once()
        orchestrator_multimodal.multimodal.get_email.assert_called_once()


class TestEjecutarTenencia:
    """Lines 160-177: _ejecutar_tenencia con/sin número de serie."""

    @pytest.mark.asyncio
    async def test_sin_serie(self, orchestrator):
        inputs = ["ABC123", "n"]
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator._ejecutar_tenencia("text")
        assert result == {"status": "ok"}
        orchestrator._modules["tenencia"].consultar.assert_awaited_once_with(
            placa="ABC123", numero_serie=None
        )

    @pytest.mark.asyncio
    async def test_con_serie(self, orchestrator):
        inputs = ["ABC123", "s", "VIN123456"]
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator._ejecutar_tenencia("text")
        assert result == {"status": "ok"}
        orchestrator._modules["tenencia"].consultar.assert_awaited_once_with(
            placa="ABC123", numero_serie="VIN123456"
        )

    @pytest.mark.asyncio
    async def test_con_multimodal(self, orchestrator_multimodal):
        """Line 163: _ejecutar_tenencia con multimodal."""
        with patch("builtins.input", return_value="n"):
            result = await orchestrator_multimodal._ejecutar_tenencia("text")
        assert result == {"status": "ok"}
        orchestrator_multimodal.multimodal.get_placa.assert_called_once()


class TestModoInteractivo:
    """Lines 216-274: menú interactivo."""

    def test_exit_opcion_0(self, orchestrator):
        """Option 0 exits."""
        with patch("builtins.input", return_value="0"):
            orchestrator.modo_interactivo_sync()
        # no exception = exited cleanly via break

    def test_curp_opcion_1(self, orchestrator):
        """Option 1 calls ejecutar_tramite('curp')."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["1", "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        mock_et.assert_any_call("curp", "text")

    def test_nss_opcion_2(self, orchestrator):
        """Option 2 calls ejecutar_tramite('nss')."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["2", "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        mock_et.assert_any_call("nss", "text")

    def test_antecedentes_opcion_3(self, orchestrator):
        """Option 3 calls ejecutar_tramite('antecedentes')."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["3", "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        mock_et.assert_any_call("antecedentes", "text")

    def test_tenencia_opcion_4(self, orchestrator):
        """Option 4 calls ejecutar_tramite('tenencia')."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["4", "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        mock_et.assert_any_call("tenencia", "text")

    def test_ambos_opcion_5(self, orchestrator):
        """Option 5 calls ejecutar_tramite('ambos')."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["5", "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        mock_et.assert_any_call("ambos", "text")

    def test_opcion_invalida(self, orchestrator):
        """Invalid option prints message and continues."""
        with patch("builtins.input", side_effect=["99", "0"]):
            orchestrator.modo_interactivo_sync()
        # continues to next iteration, no crash

    def test_keyboard_interrupt(self, orchestrator):
        """KeyboardInterrupt caught during tramite."""
        mock_et = AsyncMock(side_effect=KeyboardInterrupt)
        with patch("builtins.input", side_effect=["1", "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        # KeyboardInterrupt caught, loop continues to option 0

    def test_exception_caught(self, orchestrator):
        """Generic exception during tramite shows message."""
        mock_et = AsyncMock(side_effect=ValueError("test error"))
        with patch("builtins.input", side_effect=["1", "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        # Error printed, loop continues to option 0

    def test_multimodal_selecciona_texto(self, orchestrator_multimodal):
        """Multimodal: opción 1 (texto) por defecto."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["1", "1", "0"]):
            with patch.object(orchestrator_multimodal, "ejecutar_tramite", mock_et):
                orchestrator_multimodal.modo_interactivo_sync()
        mock_et.assert_any_call("curp", "text")

    def test_multimodal_selecciona_voz(self, orchestrator_multimodal):
        """Multimodal: opción 2 (voz)."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["1", "2", "0"]):
            with patch.object(orchestrator_multimodal, "ejecutar_tramite", mock_et):
                orchestrator_multimodal.modo_interactivo_sync()
        mock_et.assert_any_call("curp", "voice")

    def test_multimodal_selecciona_imagen(self, orchestrator_multimodal):
        """Multimodal: opción 3 (imagen)."""
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["1", "3", "0"]):
            with patch.object(orchestrator_multimodal, "ejecutar_tramite", mock_et):
                orchestrator_multimodal.modo_interactivo_sync()
        mock_et.assert_any_call("curp", "image")
