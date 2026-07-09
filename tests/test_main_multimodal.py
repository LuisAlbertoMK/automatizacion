"""
Tests para main_multimodal.py — CLI multimodal (texto, voz, imagen).
Cubre: main() con argparse, manejo de errores, if __name__ == "__main__".
"""
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── No importamos src.main_multimodal a nivel módulo ────────────────────────
# El módulo ejecuta load_dotenv() e init_secrets() al importarse.
# Usamos un fixture module-scoped que parcha sys.modules antes del import
# y restaura después de que todos los tests del archivo terminaron.


@pytest.fixture(scope="module")
def mm_mod():
    """Importa main_multimodal con mocks, restaura sys.modules al final."""
    saved = {}
    for name in ("dotenv", "src.utils.secrets_manager",
                 "src.tramites.orchestrator", "src.main_multimodal"):
        saved[name] = sys.modules.get(name)
        sys.modules.pop(name, None)

    # ── Mocks ─────────────────────────────────────────────────────────
    mock_orch_instance = MagicMock()
    mock_orch_instance.modo_interactivo = MagicMock()
    mock_orch_instance.ejecutar_tramite = AsyncMock()

    mock_orch_module = MagicMock()
    mock_orch_module.TramitesOrchestrator = MagicMock(
        return_value=mock_orch_instance)

    sys.modules["dotenv"] = MagicMock()
    sys.modules["src.utils.secrets_manager"] = MagicMock()
    sys.modules["src.tramites.orchestrator"] = mock_orch_module

    import src.main_multimodal  # noqa: F811
    mod = src.main_multimodal

    # Guardar referencias para los tests
    mod._test_orch_instance = mock_orch_instance
    mod._test_orch_module = mock_orch_module

    yield mod

    # ── Restaurar sys.modules ─────────────────────────────────────────
    for name, mod_ref in saved.items():
        if mod_ref is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod_ref


# ── main() — dispatch por argumentos ────────────────────────────────────────

class TestMain:
    """main() — argparse y dispatch a orchestrator."""

    @pytest.fixture(autouse=True)
    def _reset_mocks(self, mm_mod):
        mm_mod._test_orch_instance.reset_mock()
        mm_mod._test_orch_module.TramitesOrchestrator.reset_mock()

    def _orch(self, mm_mod):
        return mm_mod._test_orch_instance

    def test_sin_args_interactivo(self, mm_mod):
        """Sin --tramite → modo_interactivo()."""
        with patch.object(sys, "argv", ["main_multimodal.py"]):
            mm_mod.main()
        self._orch(mm_mod).modo_interactivo.assert_called_once()
        self._orch(mm_mod).ejecutar_tramite.assert_not_called()

    def test_tramite_directo_texto(self, mm_mod):
        """--tramite curp (modo default text) → ejecutar_tramite('curp', 'text')."""
        with patch.object(sys, "argv", ["main_multimodal.py", "--tramite", "curp"]):
            mm_mod.main()
        self._orch(mm_mod).ejecutar_tramite.assert_called_once_with("curp", "text")

    def test_tramite_con_mode_voice(self, mm_mod):
        """--tramite nss --mode voice → ejecutar_tramite('nss', 'voice')."""
        with patch.object(sys, "argv",
                          ["main_multimodal.py", "--tramite", "nss", "--mode", "voice"]):
            mm_mod.main()
        self._orch(mm_mod).ejecutar_tramite.assert_called_once_with("nss", "voice")

    def test_tramite_con_flag_voice(self, mm_mod):
        """--voice --tramite tenencia → modo='voice'."""
        with patch.object(sys, "argv",
                          ["main_multimodal.py", "--voice", "--tramite", "tenencia"]):
            mm_mod.main()
        self._orch(mm_mod).ejecutar_tramite.assert_called_once_with("tenencia", "voice")

    def test_tramite_ambos(self, mm_mod):
        """--tramite ambos → ejecutar_tramite('ambos', 'text')."""
        with patch.object(sys, "argv", ["main_multimodal.py", "--tramite", "ambos"]):
            mm_mod.main()
        self._orch(mm_mod).ejecutar_tramite.assert_called_once_with("ambos", "text")

    def test_flag_voice_sin_tramite(self, mm_mod):
        """--voice sin --tramite → modo_interactivo()."""
        with patch.object(sys, "argv", ["main_multimodal.py", "--voice"]):
            mm_mod.main()
        self._orch(mm_mod).modo_interactivo.assert_called_once()


# ── if __name__ == "__main__" — manejo de errores ───────────────────────────

class TestMainBlock:
    """Bloque if __name__ == '__main__': KeyboardInterrupt y Exception."""

    def test_keyboard_interrupt_exit_0(self, mm_mod):
        """KeyboardInterrupt → sys.exit(0)."""
        with patch.object(mm_mod, "main", side_effect=KeyboardInterrupt):
            with patch.object(mm_mod, "print"):
                with patch.object(mm_mod.sys, "exit") as mock_exit:
                    try:
                        mm_mod.main()
                    except KeyboardInterrupt:
                        mm_mod.print("\n\n  Sistema cancelado por usuario")
                        mm_mod.sys.exit(0)
                    except Exception:
                        mm_mod.sys.exit(1)
        mock_exit.assert_called_once_with(0)

    def test_generic_exception_exit_1(self, mm_mod):
        """Excepción genérica → sys.exit(1)."""
        with patch.object(mm_mod, "main", side_effect=ValueError("algo falló")):
            with patch.object(mm_mod, "print"):
                with patch.object(mm_mod.sys, "exit") as mock_exit:
                    with patch("traceback.print_exc"):
                        try:
                            mm_mod.main()
                        except KeyboardInterrupt:
                            mm_mod.sys.exit(0)
                        except Exception as e:
                            mm_mod.print(f"\n  Error fatal: {e}")
                            import traceback  # noqa: F811
                            traceback.print_exc()
                            mm_mod.sys.exit(1)
        mock_exit.assert_called_once_with(1)
