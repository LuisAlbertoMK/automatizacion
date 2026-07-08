"""Tests para src/main.py — CLI del agente."""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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

        import src.main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert out == ""

    @patch.dict(os.environ, {}, clear=True)
    def test_warns_storage_key_missing(self, capsys):
        import importlib

        import src.main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert "STORAGE_KEY" in out

    @patch.dict(os.environ, {"CAPTCHA_API_KEY": "tu_api_key_aqui", "STORAGE_KEY": "x"}, clear=True)
    def test_warns_captcha_api_key_placeholder(self, capsys):
        import importlib

        import src.main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert "CAPTCHA_API_KEY" in out

    @patch.dict(os.environ, {"CAPTCHA_API_KEY": "", "STORAGE_KEY": ""}, clear=True)
    def test_warns_both_missing(self, capsys):
        import importlib

        import src.main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._validar_config()
        out, _ = capsys.readouterr()
        assert "STORAGE_KEY" in out
        assert "CAPTCHA_API_KEY" in out


# ── _listar_tramites ──────────────────────────────────────────────────────────

class TestListarTramitesCLI:
    @patch("src.tramites.orchestrator.listar_tramites")
    def test_listar_prints_tramites(self, mock_listar, capsys):
        mock_listar.return_value = {
            "curp": {"modulo": "CURPModule", "estado": "✅ Producción", "tiempo": "~16s"},
        }
        import importlib

        import src.main as main_mod
        main_mod = importlib.reload(main_mod)
        main_mod._listar_tramites()
        out, _ = capsys.readouterr()
        assert "curp" in out
        assert "Producción" in out


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:
    """Test del entry point principal con argumentos mockeados."""

    @patch("src.main._listar_tramites")
    def test_list_tramites_flag(self, mock_listar):
        """--list-tramites llama a _listar_tramites y retorna."""
        import src.main as main_mod
        with patch.object(sys, "argv", ["main.py", "--list-tramites"]):
            with patch("src.main._validar_config"):
                with patch("src.main.asyncio.run"):
                    main_mod.main()
        mock_listar.assert_called_once()

    @patch("src.main.asyncio.run")
    def test_direct_mode(self, mock_asyncio_run):
        """--tramite curp llama a asyncio.run."""
        import src.main as main_mod
        with patch.object(sys, "argv", ["main.py", "--tramite", "curp", "--curp", "GALJ800101HDFXXXX0"]):
            with patch("src.main._validar_config"):
                main_mod.main()
        mock_asyncio_run.assert_called_once()
        arg = mock_asyncio_run.call_args[0][0]
        assert arg.__name__ == "modo_directo"

    @patch("src.main.asyncio.run", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_handling(self, mock_asyncio_run):
        """KeyboardInterrupt se captura graceful."""
        import src.main as main_mod
        with patch.object(sys, "argv", ["main.py", "--tramite", "curp", "--curp", "GALJ800101HDFXXXX0"]):
            with patch("src.main._validar_config"):
                main_mod.main()

    @patch("src.main.asyncio.run", side_effect=asyncio.CancelledError)
    def test_cancelled_error_handling(self, mock_asyncio_run):
        """CancelledError se captura graceful."""
        import src.main as main_mod
        with patch.object(sys, "argv", ["main.py", "--tramite", "curp", "--curp", "GALJ800101HDFXXXX0"]):
            with patch("src.main._validar_config"):
                main_mod.main()

    @patch("src.main.asyncio.run")
    def test_interactive_mode(self, mock_asyncio_run):
        """Sin args → modo interactivo."""
        import src.main as main_mod
        with patch.object(sys, "argv", ["main.py"]):
            with patch("src.main._validar_config"):
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

        import src.main as main_mod
        main_mod = importlib.reload(main_mod)

        flags = [
            ["main.py", "--list-tramites"],
            ["main.py", "--tramite", "curp"],
            ["main.py", "--tramite", "nss"],
            ["main.py", "--tramite", "ambos"],
            ["main.py", "--curp", "GODE561231HDFLRN03"],
            ["main.py", "--correo", "a@b.com"],
            ["main.py", "--perfil", "juan"],
        ]
        for argv in flags:
            with patch.object(sys, "argv", argv):
                with patch("src.main._validar_config"):
                    with patch("src.main.asyncio.run"):
                        main_mod.main()
        # Si llegamos acá, ningún flag causó error


# ── _init_services — Agente startup ──────────────────────────────────────

class TestAgenteInitServices:
    """Agente._init_services() según configuración del entorno."""

    # ── Helper: importar main con entorno limpio ──────────────────────

    def _fresh_main(self, env=None):
        """Importa main con env dado y parches default."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        if env:
            with patch.dict(os.environ, env, clear=True):
                m = importlib.reload(m)
        return m

    # ── Sin API key ni mail ──────────────────────────────────────────

    @patch.dict(os.environ, {}, clear=True)
    def test_no_services(self):
        """Sin CAPTCHA_API_KEY, sin IMAP → solver=None, mail_reader=None."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch.object(m, "CaptchaSolver") as mock_cs:
            agente = m.Agente()
            assert agente.solver is None
            assert agente.mail_reader is None
            mock_cs.assert_not_called()

    # ── Solo CaptchaSolver (pago) ────────────────────────────────────

    @patch.dict(os.environ, {"CAPTCHA_API_KEY": "real_apikey_123", "STORAGE_KEY": "x"}, clear=True)
    def test_creates_captcha_solver(self):
        """Con CAPTCHA_API_KEY válida → CaptchaSolver(api_key)."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver") as mock_cls:
            m.Agente()
            mock_cls.assert_called_once_with("real_apikey_123")

    @patch.dict(os.environ, {"CAPTCHA_API_KEY": "real_apikey_123", "STORAGE_KEY": "x"}, clear=True)
    def test_captcha_solver_error_caught(self):
        """CaptchaError en CaptchaSolver se captura y solver=None, sin fallback."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver") as mock_cs, \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            mock_cs.side_effect = m.CaptchaError("falló")
            agente = m.Agente()
            assert agente.solver is None

    # ── FreeCaptchaSolver fallback ───────────────────────────────────

    @patch.dict(os.environ, {}, clear=True)
    def test_free_solver_fallback(self):
        """Sin CAPTCHA_API_KEY, FREE_SOLVER_AVAILABLE → FreeCaptchaSolver()."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", True), \
             patch.object(m, "FreeCaptchaSolver") as mock_cls:
            m.Agente()
            mock_cls.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    def test_free_solver_error_caught(self):
        """Error en FreeCaptchaSolver se captura → solver=None."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", True), \
             patch.object(m, "FreeCaptchaSolver", side_effect=RuntimeError("fail")):
            agente = m.Agente()
            assert agente.solver is None

    @patch.dict(os.environ, {}, clear=True)
    def test_no_solver_message(self):
        """Sin ningún solver disponible → mensaje de captcha manual."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            agente = m.Agente()
            assert agente.solver is None

    # ── MailReader ───────────────────────────────────────────────────

    @patch.dict(os.environ, {
        "CAPTCHA_API_KEY": "real_apikey_123", "STORAGE_KEY": "x",
        "IMAP_EMAIL": "realuser@gmail.com", "IMAP_PASSWORD": "realsecret",
    }, clear=True)
    def test_creates_mail_reader(self):
        """IMAP config válido → MailReader()."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", True), \
             patch.object(m, "MailReader") as mock_cls:
            m.Agente()
            mock_cls.assert_called_once()

    @patch.dict(os.environ, {
        "CAPTCHA_API_KEY": "real_apikey_123", "STORAGE_KEY": "x",
        "IMAP_EMAIL": "tucorreo@gmail.com", "IMAP_PASSWORD": "secret",
    }, clear=True)
    def test_placeholder_email_skips_mail_reader(self):
        """Email placeholder ('tucorreo') → NO MailReader."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", True):
            agente = m.Agente()
            assert agente.mail_reader is None

    @patch.dict(os.environ, {
        "IMAP_EMAIL": "your-email@example.com", "IMAP_PASSWORD": "x",
    }, clear=True)
    def test_placeholder_detected_multiple_patterns(self):
        """'your-email' y '@example.com' también se detectan como placeholder."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "MAIL_AVAILABLE", True):
            agente = m.Agente()
            assert agente.mail_reader is None

    @patch.dict(os.environ, {"IMAP_EMAIL": "", "IMAP_PASSWORD": ""}, clear=True)
    def test_empty_email_skips_mail_reader(self):
        """Email vacío → NO MailReader."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "MAIL_AVAILABLE", True):
            agente = m.Agente()
            assert agente.mail_reader is None

    @patch.dict(os.environ, {
        "IMAP_EMAIL": "realuser@gmail.com", "IMAP_PASSWORD": "realsecret",
    }, clear=True)
    def test_mail_reader_error_caught(self):
        """MailReader exception se captura → mail_reader=None."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", True), \
             patch.object(m, "MailReader", side_effect=RuntimeError("conn fail")):
            agente = m.Agente()
            assert agente.mail_reader is None


# ── helpers: _validar_curp, _pedir_dato, _mostrar_resultado ─────────────

class TestValidarCurp:
    """_validar_curp() — validación de formato CURP."""

    def _get_agente(self):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            ag = m.Agente()
        return ag

    # Casos válidos
    @pytest.mark.parametrize("curp", [
        "GALJ800101HDFXXXX0",
        "OOLL940914HMCRGS08",
        "HECA561220MDFLRN09",
    ])
    def test_valid_curp(self, curp):
        agente = self._get_agente()
        assert agente._validar_curp(curp)

    # Casos inválidos
    @pytest.mark.parametrize("curp", [
        "",                     # vacío
        "123",                  # muy corto
        "GALJ800101HDFXXXX",    # 17 chars
        "GALJ800101HDFXXXX01",  # 19 chars
        "galj800101hdfxxxx01",  # minúsculas (internamente se pasa a upper)
        "GALJ800101HDFXXXX0!",  # carácter inválido
    ])
    def test_invalid_curp(self, curp):
        agente = self._get_agente()
        assert not agente._validar_curp(curp)


class TestPedirDato:
    """_pedir_dato() — input loop con validación."""

    def _get_agente(self):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            return m.Agente()

    def test_simple_input(self):
        agente = self._get_agente()
        with patch("builtins.input", return_value="GALJ800101HDFXXXX0"):
            result = agente._pedir_dato("CURP")
        assert result == "GALJ800101HDFXXXX0"

    def test_with_default(self):
        agente = self._get_agente()
        with patch("builtins.input", return_value=""):
            result = agente._pedir_dato("CURP", default="GALJ800101HDFXXXX0")
        assert result == "GALJ800101HDFXXXX0"

    def test_with_validation_passes(self):
        agente = self._get_agente()
        with patch("builtins.input", return_value="a@b.com"):
            result = agente._pedir_dato("Email", validar=lambda x: "@" in x)
        assert result == "a@b.com"

    def test_validation_fails_then_passes(self):
        agente = self._get_agente()
        inputs = iter(["notanemail", "valid@email.com"])
        with patch("builtins.input", side_effect=inputs):
            result = agente._pedir_dato("Email", validar=lambda x: "@" in x)
        assert result == "valid@email.com"

    def test_empty_no_default_retry(self):
        agente = self._get_agente()
        inputs = iter(["", "finally"])
        with patch("builtins.input", side_effect=inputs):
            result = agente._pedir_dato("Campo")
        assert result == "finally"


class TestMostrarResultado:
    """_mostrar_resultado() — formatea output de resultados."""

    def _get_agente(self):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            return m.Agente()

    def test_with_values(self, capsys):
        agente = self._get_agente()
        agente._mostrar_resultado("CURP", {"curp": "GALJ800101...", "pdf_path": "/tmp/c.pdf"})
        out, _ = capsys.readouterr()
        assert "RESULTADO" in out
        assert "CURP" in out  # both the tipo and the key name contain "CURP"
        assert "GALJ800101" in out
        assert "PDF_PATH" in out  # k.upper()

    def test_empty_values_omitted(self, capsys):
        agente = self._get_agente()
        agente._mostrar_resultado("TEST", {"ok": "", "nok": None, "val": "real"})
        out, _ = capsys.readouterr()
        assert "VAL" in out  # k.upper()
        assert "real" in out
        # Empty/None keys should NOT appear — no OK or NOK in output
        assert "OK:" not in out
        assert "NOK:" not in out


# ── tramite_curp ─────────────────────────────────────────────────────────

class TestTramiteCurp:
    """Agente.tramite_curp() — consulta CURP."""

    async def test_with_perfil(self):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock(return_value={"curp": "GALJ800101...", "pdf_path": "/tmp/c.pdf"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.curp.CURPModule") as mock_curp:
            mock_curp.return_value = mock_mod
            agente = m.Agente()
            perfil = {"curp": "GALJ800101HDFXXXX0"}
            result = await agente.tramite_curp(perfil=perfil)
        assert result["curp"] == "GALJ800101..."

    async def test_without_perfil(self):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock(return_value={"curp": "GALJ800101...", "pdf_path": "/tmp/c.pdf"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.curp.CURPModule") as mock_curp, \
             patch("builtins.input", return_value="GALJ800101HDFXXXX0"):
            mock_curp.return_value = mock_mod
            agente = m.Agente()
            result = await agente.tramite_curp(perfil=None)
        assert result["curp"] == "GALJ800101..."


# ── gestionar_perfil ─────────────────────────────────────────────────────

class TestGestionarPerfil:
    """Agente.gestionar_perfil() — menú de perfiles."""

    def _make_agente(self):
        import src.main as m
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            return m.Agente(), m

    def test_save_new_profile(self):
        agente, m = self._make_agente()
        with patch.object(m, "save_profile") as mock_save, \
             patch.object(m, "list_profiles", return_value=[]), \
             patch("builtins.input", side_effect=iter([
                 "1", "juan_garcia", "GALJ800101HDFXXXX0",
                 "juan@mail.com", "ABC123", "Juan García",
             ])):
            result = agente.gestionar_perfil()
        assert result is not None
        assert result["curp"] == "GALJ800101HDFXXXX0"
        assert result["correo"] == "juan@mail.com"
        mock_save.assert_called_once()

    def test_load_existing_profile(self):
        agente, m = self._make_agente()
        with patch.object(m, "list_profiles", return_value=["juan", "maria"]), \
             patch.object(m, "load_profile", return_value={
                 "curp": "GALJ800101HDFXXXX0", "correo": "juan@mail.com",
             }), \
             patch("builtins.input", side_effect=iter(["2", "1"])):
            result = agente.gestionar_perfil()
        assert result is not None
        assert result["curp"] == "GALJ800101HDFXXXX0"

    def test_load_no_profiles(self):
        agente, m = self._make_agente()
        with patch.object(m, "list_profiles", return_value=[]), \
             patch("builtins.input", return_value="2"):
            result = agente.gestionar_perfil()
        assert result is None

    def test_list_profiles(self, capsys):
        agente, m = self._make_agente()
        with patch.object(m, "list_profiles", return_value=["juan", "maria"]), \
             patch("builtins.input", return_value="3"):
            result = agente.gestionar_perfil()
        assert result is None
        out, _ = capsys.readouterr()
        assert "juan" in out
        assert "maria" in out

    def test_list_no_profiles(self, capsys):
        agente, m = self._make_agente()
        with patch.object(m, "list_profiles", return_value=[]), \
             patch("builtins.input", return_value="3"):
            result = agente.gestionar_perfil()
        assert result is None
        out, _ = capsys.readouterr()
        assert "No hay perfiles guardados" in out

    def test_invalid_option(self):
        agente, m = self._make_agente()
        with patch.object(m, "list_profiles", return_value=["juan"]), \
             patch("builtins.input", return_value="999"):
            result = agente.gestionar_perfil()
        assert result is None

    def test_load_invalid_index(self, capsys):
        """Opción 2 con índice fuera de rango → IndexError → lines 275-277."""
        agente, m = self._make_agente()
        with patch.object(m, "list_profiles", return_value=["juan"]), \
             patch("builtins.input", side_effect=["2", "999"]):
            result = agente.gestionar_perfil()
        assert result is None
        out, _ = capsys.readouterr()
        assert "Selección inválida" in out


# ── tramite_nss ──────────────────────────────────────────────────────────

class TestTramiteNss:
    """Agente.tramite_nss() — consulta NSS IMSS (líneas 156-195)."""

    async def test_with_perfil_nss_sent_to_email(self, capsys):
        """NSS enviado al correo → muestra instrucciones."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock(return_value={"nss": "ENVIADO_AL_CORREO"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls, \
             patch("builtins.input", return_value=""):
            mock_nss_cls.return_value = mock_mod
            agente = m.Agente()
            result = await agente.tramite_nss(perfil={"curp": "GALJ800101HDFXXXX0", "correo": "a@b.com"})
        assert result["nss"] == "ENVIADO_AL_CORREO"
        out, _ = capsys.readouterr()
        assert "SOLICITUD ENVIADA" in out
        assert "a***@b.com" in out

    async def test_with_perfil_nss_found(self, capsys):
        """NSS encontrado → _mostrar_resultado con el resultado."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock(return_value={"nss": "12345678901", "curp": "GALJ800101..."})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls, \
             patch("builtins.input", return_value=""):
            mock_nss_cls.return_value = mock_mod
            agente = m.Agente()
            result = await agente.tramite_nss(perfil={"curp": "GALJ800101HDFXXXX0", "correo": "a@b.com"})
        assert result["nss"] == "12345678901"
        out, _ = capsys.readouterr()
        assert "NSS" in out
        assert "12345678901" in out

    async def test_without_perfil_prompts_curp_and_correo(self):
        """Sin perfil → pide CURP y correo via _pedir_dato."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock(return_value={"nss": "12345678901"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls, \
             patch("builtins.input", side_effect=[
                 "GALJ800101HDFXXXX0",  # CURP prompt
                 "a@b.com",              # Correo prompt
             ]):
            mock_nss_cls.return_value = mock_mod
            agente = m.Agente()
            result = await agente.tramite_nss(perfil=None)
        assert result["nss"] == "12345678901"
        mock_mod.consultar.assert_awaited_once_with(
            curp="GALJ800101HDFXXXX0",
            correo="a@b.com",
        )

    async def test_uses_profile_correo_as_default(self):
        """Perfil con correo → muestra hint con correo_default."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock(return_value={"nss": "12345678901"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls, \
             patch("builtins.input", return_value=""):
            mock_nss_cls.return_value = mock_mod
            agente = m.Agente()
            result = await agente.tramite_nss(
                perfil={"curp": "GALJ800101HDFXXXX0", "correo": "default@mail.com"}
            )
        # Empty input with default → usa default del perfil
        assert result["nss"] == "12345678901"

    async def test_no_mail_reader_shows_warning(self, capsys):
        """Sin mail_reader → muestra advertencia."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock(return_value={"nss": "12345678901"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls, \
             patch("builtins.input", return_value=""):
            mock_nss_cls.return_value = mock_mod
            agente = m.Agente()
            assert agente.mail_reader is None
            await agente.tramite_nss(perfil={"curp": "GALJ800101HDFXXXX0", "correo": "a@b.com"})
        out, _ = capsys.readouterr()
        assert "Sin lector de correo" in out


# ── tramite_ambos ────────────────────────────────────────────────────────

class TestTramiteAmbos:
    """Agente.tramite_ambos() — CURP + NSS secuencial (líneas 200-237)."""

    async def test_both_with_perfil(self, capsys):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_curp = MagicMock()
        mock_curp.consultar = AsyncMock(return_value={"curp": "GALJ800101...", "pdf_path": "/tmp/c.pdf"})
        mock_nss = MagicMock()
        mock_nss.consultar = AsyncMock(return_value={"nss": "12345678901"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.curp.CURPModule") as mock_curp_cls, \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls, \
             patch("builtins.input", return_value=""):
            mock_curp_cls.return_value = mock_curp
            mock_nss_cls.return_value  = mock_nss
            agente = m.Agente()
            result = await agente.tramite_ambos(
                perfil={"curp": "GALJ800101HDFXXXX0", "correo": "a@b.com"}
            )
        assert result["curp"]["curp"] == "GALJ800101..."
        assert result["nss"]["nss"]  == "12345678901"
        out, _ = capsys.readouterr()
        assert "RESUMEN FINAL" in out
        assert "/tmp/c.pdf" in out

    async def test_both_without_perfil(self):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_curp = MagicMock()
        mock_curp.consultar = AsyncMock(return_value={"curp": "GALJ800101..."})
        mock_nss = MagicMock()
        mock_nss.consultar = AsyncMock(return_value={"nss": "12345678901"})
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.curp.CURPModule") as mock_curp_cls, \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls, \
             patch("builtins.input", side_effect=[
                 "GALJ800101HDFXXXX0",  # CURP prompt
                 "a@b.com",              # Correo prompt
             ]):
            mock_curp_cls.return_value = mock_curp
            mock_nss_cls.return_value  = mock_nss
            agente = m.Agente()
            result = await agente.tramite_ambos(perfil=None)
        assert result["curp"]["curp"] == "GALJ800101..."
        assert result["nss"]["nss"]  == "12345678901"


# ── modo_interactivo ─────────────────────────────────────────────────────

class TestModoInteractivo:
    """modo_interactivo() — REPL interactivo (líneas 317-363)."""

    async def test_curp_command(self):
        """Comando 'curp' → llama a agente.tramite_curp."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_curp = AsyncMock()
        mock_agente.tramite_nss = AsyncMock()
        mock_agente.tramite_ambos = AsyncMock()
        mock_agente.gestionar_perfil = MagicMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["curp", "salir"]):
            await m.modo_interactivo()
        mock_agente.tramite_curp.assert_awaited_once()

    async def test_nss_command(self):
        """Comando 'nss' → llama a agente.tramite_nss."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_curp = AsyncMock()
        mock_agente.tramite_nss = AsyncMock()
        mock_agente.tramite_ambos = AsyncMock()
        mock_agente.gestionar_perfil = MagicMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["nss", "salir"]):
            await m.modo_interactivo()
        mock_agente.tramite_nss.assert_awaited_once()

    async def test_ambos_command(self):
        """Comando 'ambos' → llama a agente.tramite_ambos."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_curp = AsyncMock()
        mock_agente.tramite_nss = AsyncMock()
        mock_agente.tramite_ambos = AsyncMock()
        mock_agente.gestionar_perfil = MagicMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["ambos", "salir"]):
            await m.modo_interactivo()
        mock_agente.tramite_ambos.assert_awaited_once()

    async def test_ayuda_command(self, capsys):
        """Comando 'ayuda' → imprime AYUDA."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_curp = AsyncMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", "TEXT_AYUDA"), \
             patch("builtins.input", side_effect=["ayuda", "salir"]):
            await m.modo_interactivo()
        out, _ = capsys.readouterr()
        assert "TEXT_AYUDA" in out

    async def test_natural_language_curp_nss(self):
        """Lenguaje natural con 'curp' y 'nss' → tramite_ambos."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_ambos = AsyncMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["quiero curp y nss", "salir"]):
            await m.modo_interactivo()
        mock_agente.tramite_ambos.assert_awaited_once()

    async def test_natural_language_curp_only(self):
        """Lenguaje natural con solo 'curp' → tramite_curp."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_curp = AsyncMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["necesito mi curp", "salir"]):
            await m.modo_interactivo()
        mock_agente.tramite_curp.assert_awaited_once()

    async def test_natural_language_nss(self):
        """Lenguaje natural con 'seguro' → tramite_nss."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_nss = AsyncMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["quiero mi seguro social", "salir"]):
            await m.modo_interactivo()
        mock_agente.tramite_nss.assert_awaited_once()

    async def test_exit_command(self, capsys):
        """Comando 'exit' → sale del loop."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "Agente") as mock_cls, \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", return_value="exit"):
            mock_agente = MagicMock()
            mock_cls.return_value = mock_agente
            await m.modo_interactivo()
        out, _ = capsys.readouterr()
        assert "Hasta luego" in out

    async def test_unknown_command(self, capsys):
        """Comando no reconocido → mensaje de error."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["xyz123", "salir"]):
            await m.modo_interactivo()
        out, _ = capsys.readouterr()
        assert "no reconocido" in out

    async def test_keyboard_interrupt(self, capsys):
        """KeyboardInterrupt durante comando → except handler lines 362-363."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_curp = AsyncMock(side_effect=KeyboardInterrupt)
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["curp", "salir"]):
            await m.modo_interactivo()
        out, _ = capsys.readouterr()
        assert "Interrumpido" in out

    async def test_perfil_command_loads_profile(self):
        """Comando 'perfil' → llama a gestionar_perfil y carga perfil."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        perfil_data = {"curp": "GALJ800101HDFXXXX0", "correo": "a@b.com"}
        mock_agente = MagicMock()
        mock_agente.gestionar_perfil = MagicMock(return_value=perfil_data)
        mock_agente.tramite_curp = AsyncMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=["juan"]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["perfil", "curp", "salir"]):
            await m.modo_interactivo()
        mock_agente.gestionar_perfil.assert_called_once()
        mock_agente.tramite_curp.assert_awaited_once()

    async def test_exception_during_command(self, capsys):
        """Excepción en comando → except Exception handler lines 362-363."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        mock_agente.tramite_curp = AsyncMock(side_effect=ValueError("algo salió mal"))
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["curp", "salir"]):
            await m.modo_interactivo()
        out, _ = capsys.readouterr()
        assert "Error" in out
        assert "algo salió mal" in out

    async def test_empty_line_skips(self):
        """Línea vacía → continúa sin hacer nada."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_agente = MagicMock()
        with patch.object(m, "Agente", return_value=mock_agente), \
             patch.object(m, "list_profiles", return_value=[]), \
             patch.object(m, "BANNER", ""), \
             patch.object(m, "AYUDA", ""), \
             patch("builtins.input", side_effect=["", "salir"]):
            await m.modo_interactivo()
        # Sin assertions extra — verifica que no crashea


# ── modo_directo ─────────────────────────────────────────────────────────

class TestModoDirecto:
    """modo_directo() — ejecución sin interacción."""

    @patch("src.main.asyncio.run")
    def test_direct_curp_with_args(self, mock_run):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(sys, "argv", ["main.py", "--tramite", "curp", "--curp", "GALJ800101HDFXXXX0"]):
            with patch.object(m, "_validar_config"):
                m.main()
        # asyncio.run was called with modo_directo
        args, _ = mock_run.call_args
        coro_fn = args[0]
        assert coro_fn.__name__ == "modo_directo"

    @patch("src.main.asyncio.run")
    def test_direct_nss_with_args(self, mock_run):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(sys, "argv", [
            "main.py", "--tramite", "nss",
            "--curp", "GALJ800101HDFXXXX0", "--correo", "a@b.com",
        ]):
            with patch.object(m, "_validar_config"):
                m.main()
        args, _ = mock_run.call_args
        coro_fn = args[0]
        assert coro_fn.__name__ == "modo_directo"

    @patch("src.main.asyncio.run")
    def test_direct_perfil_mode(self, mock_run):
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(sys, "argv", ["main.py", "--perfil", "juan"]):
            with patch.object(m, "_validar_config"):
                m.main()
        args, _ = mock_run.call_args
        coro_fn = args[0]
        assert coro_fn.__name__ == "modo_directo"


class TestModoDirectoExecution:
    """modo_directo() — ejecución real con módulos mockeados (líneas 368-393)."""

    async def test_curp_execution(self):
        """--tramite curp → crea CURPModule y llama consultar."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock()
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.curp.CURPModule") as mock_curp_cls:
            mock_curp_cls.return_value = mock_mod
            args = MagicMock(tramite="curp", curp="GALJ800101HDFXXXX0", correo=None, perfil=None)
            await m.modo_directo(args)
        mock_curp_cls.assert_called_once()
        mock_mod.consultar.assert_awaited_once_with(curp="GALJ800101HDFXXXX0")

    async def test_nss_execution(self):
        """--tramite nss → crea NSSModule y llama consultar."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock()
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.nss.NSSModule") as mock_nss_cls:
            mock_nss_cls.return_value = mock_mod
            args = MagicMock(
                tramite="nss", curp="GALJ800101HDFXXXX0",
                correo="a@b.com", perfil=None,
            )
            await m.modo_directo(args)
        mock_nss_cls.assert_called_once()
        mock_mod.consultar.assert_awaited_once_with(
            curp="GALJ800101HDFXXXX0", correo="a@b.com",
        )

    async def test_curp_from_perfil(self):
        """--tramite curp sin --curp → usa perfil."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        mock_mod = MagicMock()
        mock_mod.consultar = AsyncMock()
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch("src.tramites.curp.CURPModule") as mock_curp_cls, \
             patch.object(m, "load_profile", return_value={
                 "curp": "PERFIL_CURP", "correo": "perfil@mail.com",
             }):
            mock_curp_cls.return_value = mock_mod
            args = MagicMock(tramite="curp", curp=None, correo=None, perfil="juan")
            await m.modo_directo(args)
        mock_mod.consultar.assert_awaited_once_with(curp="PERFIL_CURP")

    async def test_curp_missing_curp_exits(self):
        """--tramite curp sin --curp ni perfil → sys.exit(1) (lines 380-381)."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            args = MagicMock(tramite="curp", curp=None, correo=None, perfil=None)
            with pytest.raises(SystemExit):
                await m.modo_directo(args)

    async def test_nss_missing_curp_exits(self):
        """--tramite nss sin CURP ni perfil → sys.exit(1)."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False):
            args = MagicMock(tramite="nss", curp=None, correo=None, perfil=None)
            with pytest.raises(SystemExit):
                await m.modo_directo(args)

    async def test_perfil_not_found_exits(self):
        """Perfil inexistente → sys.exit(1)."""
        import importlib

        import src.main as m
        m = importlib.reload(m)
        with patch.object(m, "CaptchaSolver"), \
             patch.object(m, "MAIL_AVAILABLE", False), \
             patch.object(m, "FREE_SOLVER_AVAILABLE", False), \
             patch.object(m, "load_profile", return_value=None):
            args = MagicMock(tramite=None, curp=None, correo=None, perfil="no_existe")
            with pytest.raises(SystemExit):
                await m.modo_directo(args)
