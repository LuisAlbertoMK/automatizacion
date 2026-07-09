"""Tests para src/tramites/orchestrator.py — orquestador de trámites."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tramites.orchestrator import TRAMITES_REGISTRADOS, listar_tramites  # noqa: E402

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
    from src.tramites.orchestrator import TramitesOrchestrator
    with patch("src.tramites.orchestrator.MULTIMODAL_AVAILABLE", False):
        orch = TramitesOrchestrator()
    orch._modules = _mock_modules
    return orch


@pytest.fixture
def orchestrator_multimodal(mock_multimodal, _mock_modules):
    """TramitesOrchestrator con entrada multimodal."""
    from src.tramites.orchestrator import TramitesOrchestrator
    with patch("src.tramites.orchestrator.MultimodalInput", return_value=mock_multimodal):
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


# ── _get_module — import bajo demanda y cache ───────────────────────────────

class TestGetModule:
    """_get_module — import dinámico y caching (lines 92-104)."""

    def test_cache_hit(self, orchestrator):
        """Cuando ya está en _modules, retorna sin importar."""
        mod = orchestrator._get_module("curp")
        assert mod is orchestrator._modules["curp"]

    def test_importa_y_cachea(self):
        """Importa bajo demanda y guarda en _modules."""
        from src.tramites.orchestrator import TramitesOrchestrator
        with patch("src.tramites.orchestrator.MULTIMODAL_AVAILABLE", False):
            orch = TramitesOrchestrator()
        orch._modules = {}

        with patch("importlib.import_module") as mock_import:
            mock_mod = MagicMock()
            mock_mod.CURPModule = MagicMock(
                return_value=_make_mock_module())
            mock_import.return_value = mock_mod

            mod = orch._get_module("curp")
            assert mod is not None
            assert "curp" in orch._modules
            assert orch._modules["curp"] is mod
            mock_import.assert_called_once_with("modules.curp")
            mock_mod.CURPModule.assert_called_once()

    def test_importa_nss_con_mail_reader(self):
        """_get_module('nss') pasa mail_reader en kwargs."""
        from src.tramites.orchestrator import TramitesOrchestrator
        with patch("src.tramites.orchestrator.MULTIMODAL_AVAILABLE", False):
            orch = TramitesOrchestrator()
        orch._mail_reader = MagicMock()
        orch._modules = {}

        with patch("importlib.import_module") as mock_import:
            mock_mod = MagicMock()
            mock_mod.NSSModule = MagicMock()
            mock_import.return_value = mock_mod

            orch._get_module("nss")
            _, kwargs = mock_mod.NSSModule.call_args
            assert kwargs.get("mail_reader") is orch._mail_reader

    def test_cache_evita_segundo_import(self, orchestrator):
        """Segunda llamada al mismo trámite usa cache."""
        with patch("importlib.import_module") as mock_import:
            mod1 = orchestrator._get_module("curp")
            mod2 = orchestrator._get_module("curp")
            assert mod1 is mod2
            mock_import.assert_not_called()  # cache hit, no import


# ── Trámites migrados — ejecutar_tramite + _ejecutar_* ─────────────────────

class TestEjecutarMigrados:
    """ejecutar_tramite + _ejecutar_* para rfc, acta, pasaporte, etc."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tipo, inputs", [
        ("rfc",             ["CURP123456HDF", "", "", ""]),
        ("acta_nacimiento",  ["CURP123456HDF"]),
        ("pasaporte",        ["CURP123456HDF", "", "", "", "MEX", "", ""]),
        ("semanas",          ["CURP123456HDF", ""]),
        ("control_confianza", ["CURP", "", "", "", ""]),
        ("buro",             ["RFC", "CURP", "", "", "", ""]),
        ("circulo",          ["RFC", "CURP", "", "", "", ""]),
        ("cita_ine",         ["CURP123456HDF", ""]),
        ("cita_sat",         ["RFC", "", ""]),
    ])
    async def test_ejecutar(self, orchestrator, tipo, inputs):
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator.ejecutar_tramite(tipo)
        assert result == {"status": "ok"}

    # ── Multimodal path (solo los que lo soportan) ──────────────────────

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tipo, inputs", [
        ("rfc",             ["", "", ""]),            # input para nombre/apellidos
        ("acta_nacimiento",  []),
        ("pasaporte",        ["", "", "", "MEX", "", ""]),
        ("semanas",          [""]),
        ("cita_ine",         [""]),
    ])
    async def test_ejecutar_con_multimodal(self, orchestrator_multimodal, tipo, inputs):
        """Test con multimodal disponible (solo trámites que lo usan)."""
        mock_mod = _make_mock_module()
        orchestrator_multimodal._modules[tipo] = mock_mod
        with patch("builtins.input", side_effect=inputs):
            result = await orchestrator_multimodal.ejecutar_tramite(tipo)
        assert result == {"status": "ok"}


# ── Menu interactivo — opciones 6-16 ────────────────────────────────────────

class TestMenuMigrados:
    """Options 6-16 en modo_interactivo."""

    @pytest.mark.parametrize("opcion, tramite", [
        ("6", "rfc"),
        ("7", "acta_nacimiento"),
        ("8", "pasaporte"),
        ("9", "semanas"),
        ("10", "control_confianza"),
        ("11", "buro"),
        ("12", "circulo"),
        ("13", "cita_ine"),
        ("14", "cita_sat"),
    ])
    def test_menu_migrados(self, orchestrator, opcion, tramite):
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=[opcion, "0"]):
            with patch.object(orchestrator, "ejecutar_tramite", mock_et):
                orchestrator.modo_interactivo_sync()
        mock_et.assert_any_call(tramite, "text")

    def test_menu_cv(self, orchestrator):
        """Option 15 → generar_cv_interactivo."""
        with patch.object(orchestrator, "generar_cv_interactivo", AsyncMock()) as mock_cv:
            with patch("builtins.input", side_effect=["15", "0"]):
                orchestrator.modo_interactivo_sync()
        mock_cv.assert_called_once()

    def test_menu_escrito(self, orchestrator):
        """Option 16 → generar_escrito_interactivo."""
        with patch.object(orchestrator, "generar_escrito_interactivo", AsyncMock()) as mock_esc:
            with patch("builtins.input", side_effect=["16", "0"]):
                orchestrator.modo_interactivo_sync()
        mock_esc.assert_called_once()


# ── Modalidad multimodal sin voz/OCR ────────────────────────────────────────

class TestModoInteractivoMultimodalIncompleto:
    """Lines 421-423: multimodal sin voice/ocr."""

    def test_sin_voz_falla_a_texto(self):
        """Multimodal disponible pero voice=None → opción 2 cae a modo=text."""
        from src.tramites.orchestrator import TramitesOrchestrator
        mm = MagicMock()
        mm.voice = None
        mm.ocr = True
        with patch("src.tramites.orchestrator.MultimodalInput", return_value=mm):
            with patch("src.tramites.orchestrator.MULTIMODAL_AVAILABLE", True):
                orch = TramitesOrchestrator()
        orch._modules = {"curp": _make_mock_module()}
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["1", "2", "0"]):
            with patch.object(orch, "ejecutar_tramite", mock_et):
                orch.modo_interactivo_sync()
        mock_et.assert_any_call("curp", "text")

    def test_sin_ocr_falla_a_texto(self):
        """Multimodal disponible pero ocr=None → opción 3 cae a modo=text."""
        from src.tramites.orchestrator import TramitesOrchestrator
        mm = MagicMock()
        mm.voice = True
        mm.ocr = None
        with patch("src.tramites.orchestrator.MultimodalInput", return_value=mm):
            with patch("src.tramites.orchestrator.MULTIMODAL_AVAILABLE", True):
                orch = TramitesOrchestrator()
        orch._modules = {"curp": _make_mock_module()}
        mock_et = AsyncMock(return_value={"status": "ok"})
        with patch("builtins.input", side_effect=["1", "3", "0"]):
            with patch.object(orch, "ejecutar_tramite", mock_et):
                orch.modo_interactivo_sync()
        mock_et.assert_any_call("curp", "text")


# ── Generadores de documentos ──────────────────────────────────────────────

class _ImportFailModule:
    """Simula un módulo cuyo import falla (para except ImportError)."""
    def __getattr__(self, name):
        raise ImportError(f"No module named {name}")


class TestGenerarDocumentos:
    """generar_cv_interactivo y generar_escrito_interactivo."""

    @pytest.mark.asyncio
    async def test_cv_disponible(self, orchestrator):
        with patch("src.tramites.documentos.CVGenerator") as mock_cv_cls:
            mock_cv_cls.return_value.generar_interactivo.return_value = {"status": "ok"}
            result = await orchestrator.generar_cv_interactivo()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_cv_no_disponible(self, orchestrator):
        old_mod = sys.modules.pop("src.tramites.documentos", None)
        sys.modules["src.tramites.documentos"] = _ImportFailModule()
        try:
            result = await orchestrator.generar_cv_interactivo()
            assert result["status"] == "error"
            assert "python-docx" in result.get("error", "")
        finally:
            sys.modules.pop("src.tramites.documentos", None)
            if old_mod is not None:
                sys.modules["src.tramites.documentos"] = old_mod

    @pytest.mark.asyncio
    async def test_escrito_disponible(self, orchestrator):
        with patch("src.tramites.documentos.EscritoGenerator") as mock_esc_cls:
            mock_esc_cls.return_value.generar_interactivo.return_value = {"status": "ok"}
            result = await orchestrator.generar_escrito_interactivo()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_escrito_no_disponible(self, orchestrator):
        old_mod = sys.modules.pop("src.tramites.documentos", None)
        sys.modules["src.tramites.documentos"] = _ImportFailModule()
        try:
            result = await orchestrator.generar_escrito_interactivo()
            assert result["status"] == "error"
            assert "python-docx" in result.get("error", "")
        finally:
            sys.modules.pop("src.tramites.documentos", None)
            if old_mod is not None:
                sys.modules["src.tramites.documentos"] = old_mod
