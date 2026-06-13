"""Tests para src/main.py — CLI del agente."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Fixture global: neutraliza load_dotenv ────────────────────────────────────

@pytest.fixture(autouse=True)
def _no_dotenv():
    """Evita que load_dotenv cargue config.env desde disco en todos los tests."""
    with patch("dotenv.load_dotenv"):
        yield


# ── _validar_config ───────────────────────────────────────────────────────────

class TestValidarConfig:
    """_validar_config() imprime warnings si faltan configs críticas."""

    @patch.dict(os.environ, {"STORAGE_KEY": "real_key", "CAPTCHA_API_KEY": "real_api_key"}, clear=True)
    def test_no_issues_when_configured(self, capsys):
        import importlib

        import main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert out == ""

    @patch.dict(os.environ, {}, clear=True)
    def test_warns_storage_key_missing(self, capsys):
        import importlib

        import main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert "STORAGE_KEY" in out

    @patch.dict(os.environ, {"CAPTCHA_API_KEY": "tu_api_key_aqui", "STORAGE_KEY": "x"}, clear=True)
    def test_warns_captcha_api_key_placeholder(self, capsys):
        import importlib

        import main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert "CAPTCHA_API_KEY" in out

    @patch.dict(os.environ, {"CAPTCHA_API_KEY": "", "STORAGE_KEY": ""}, clear=True)
    def test_warns_both_missing(self, capsys):
        import importlib

        import main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert "STORAGE_KEY" in out
        assert "CAPTCHA_API_KEY" in out


# ── _listar_tramites ──────────────────────────────────────────────────────────

class TestListarTramitesCLI:
    @patch("modules.orchestrator.listar_tramites")
    def test_listar_prints_tramites(self, mock_listar, capsys):
        mock_listar.return_value = {
            "curp": {"modulo": "CURPModule", "estado": "✅ Producción", "tiempo": "~16s"},
        }
        import importlib

        import main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._listar_tramites()
        out, _ = capsys.readouterr()
        assert "curp" in out
        assert "Producción" in out


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:
    """Test del entry point principal con argumentos mockeados."""

    @patch("main._listar_tramites")
    def test_list_tramites_flag(self, mock_listar):
        """--list-tramites llama a _listar_tramites y retorna."""
        import main as main_mod
        with patch.object(sys, "argv", ["main.py", "--list-tramites"]):
            with patch("main._validar_config"):
                with patch("main.asyncio.run"):
                    main_mod.main()
        mock_listar.assert_called_once()

    @patch("main.asyncio.run")
    def test_direct_mode(self, mock_asyncio_run):
        """--tramite curp llama a asyncio.run."""
        import main as main_mod
        with patch.object(sys, "argv", ["main.py", "--tramite", "curp", "--curp", "GALJ800101HDFXXXX0"]):
            with patch("main._validar_config"):
                main_mod.main()
        mock_asyncio_run.assert_called_once()
        arg = mock_asyncio_run.call_args[0][0]
        assert arg.__name__ == "modo_directo"

    @patch("main.asyncio.run", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_handling(self, mock_asyncio_run):
        """KeyboardInterrupt se captura graceful."""
        import main as main_mod
        with patch.object(sys, "argv", ["main.py", "--tramite", "curp", "--curp", "GALJ800101HDFXXXX0"]):
            with patch("main._validar_config"):
                main_mod.main()

    @patch("main.asyncio.run", side_effect=asyncio.CancelledError)
    def test_cancelled_error_handling(self, mock_asyncio_run):
        """CancelledError se captura graceful."""
        import main as main_mod
        with patch.object(sys, "argv", ["main.py", "--tramite", "curp", "--curp", "GALJ800101HDFXXXX0"]):
            with patch("main._validar_config"):
                main_mod.main()

    @patch("main.asyncio.run")
    def test_interactive_mode(self, mock_asyncio_run):
        """Sin args → modo interactivo."""
        import main as main_mod
        with patch.object(sys, "argv", ["main.py"]):
            with patch("main._validar_config"):
                main_mod.main()
        mock_asyncio_run.assert_called_once()
        arg = mock_asyncio_run.call_args[0][0]
        assert arg.__name__ == "modo_interactivo"


# ── argparse ──────────────────────────────────────────────────────────────────

class TestArgparse:
    """Verifica que argparse acepta todos los flags."""

    def test_all_flags_accepted(self):
        """Cada flag se parsea sin error."""
        import importlib

        import main as main_mod
        main_mod = importlib.reload(main_mod)

        flags = [
            ["main.py", "--list-tramites"],
            ["main.py", "--tramite", "curp"],
            ["main.py", "--tramite", "nss"],
            ["main.py", "--tramite", "ambos"],
            ["main.py", "--curp", "TEST"],
            ["main.py", "--correo", "a@b.com"],
            ["main.py", "--perfil", "juan"],
        ]
        for argv in flags:
            with patch.object(sys, "argv", argv):
                with patch("main._validar_config"):
                    with patch("main.asyncio.run"):
                        main_mod.main()
        # Si llegamos acá, ningún flag causó error
