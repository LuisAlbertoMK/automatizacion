"""Tests para src/utils/secrets_manager.py — con keyring mockeado."""

from unittest.mock import patch, MagicMock
import os
import sys

import pytest


# Mock de keyring a nivel módulo antes de importar secrets_manager
_fake_keyring = MagicMock()
_fake_keyring.get_password.return_value = None

_patches = [
    patch.dict("sys.modules", {"keyring": _fake_keyring}),
    patch("src.utils.secrets_manager.KEYRING_AVAILABLE", True),
    patch("src.utils.secrets_manager.keyring", _fake_keyring),
]
for p in _patches:
    p.start()

from src.utils.secrets_manager import (  # noqa: E402
    get_secret,
    init_secrets,
    main_cli,
    store_all,
    store_secret,
    SECRET_KEYS,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Resetea el mock y env antes de cada test."""
    _fake_keyring.reset_mock()
    _fake_keyring.get_password.return_value = None
    _fake_keyring.get_password.side_effect = None
    _fake_keyring.set_password.return_value = None
    _fake_keyring.set_password.side_effect = None
    _fake_keyring.delete_password.side_effect = None
    for key in SECRET_KEYS:
        os.environ.pop(key, None)
    yield


class TestGetSecret:
    def test_returns_from_keyring_first(self):
        _fake_keyring.get_password.return_value = "from_keyring"
        val = get_secret("CAPTCHA_API_KEY")
        assert val == "from_keyring"
        _fake_keyring.get_password.assert_called_once_with(
            "agente-tramites-gobmx", "CAPTCHA_API_KEY"
        )

    def test_fallback_to_env_when_keyring_returns_none(self):
        os.environ["CAPTCHA_API_KEY"] = "from_env"
        val = get_secret("CAPTCHA_API_KEY")
        assert val == "from_env"

    def test_returns_default_when_not_found(self):
        val = get_secret("MISSING_KEY", "default_val")
        assert val == "default_val"


class TestInitSecrets:
    def test_sets_environ_from_keyring(self):
        _fake_keyring.get_password.side_effect = (
            lambda service, key: f"val_{key}"
        )
        init_secrets()
        for key in SECRET_KEYS:
            assert os.environ.get(key) == f"val_{key}", (
                f"Expected {key} to be set"
            )

    def test_overrides_env_from_keyring(self):
        os.environ["STORAGE_KEY"] = "existing"
        _fake_keyring.get_password.return_value = "from_keyring"
        init_secrets()
        assert os.environ["STORAGE_KEY"] == "from_keyring"


class TestStoreSecret:
    def test_stores_to_keyring(self):
        result = store_secret("CAPTCHA_API_KEY", "new_value")
        assert result is True
        _fake_keyring.set_password.assert_called_once_with(
            "agente-tramites-gobmx", "CAPTCHA_API_KEY", "new_value"
        )

    def test_reads_from_env_when_value_omitted(self):
        os.environ["STORAGE_KEY"] = "env_value"
        result = store_secret("STORAGE_KEY")
        assert result is True
        _fake_keyring.set_password.assert_called_once_with(
            "agente-tramites-gobmx", "STORAGE_KEY", "env_value"
        )

    def test_returns_false_if_empty(self):
        result = store_secret("EMPTY_KEY", "")
        assert result is False


# ── init_secrets — KEYRING_AVAILABLE=False ──────────────────────────────────

class TestInitSecretsKeyringUnavailable:
    """init_secrets() con KEYRING_AVAILABLE=False → early return."""

    def test_returns_early(self):
        with patch("src.utils.secrets_manager.KEYRING_AVAILABLE", False):
            init_secrets()
        # No setea nada en os.environ (ya está limpio por reset_state)
        assert not any(os.environ.get(k) for k in SECRET_KEYS)


# ── store_secret — KEYRING_AVAILABLE=False ─────────────────────────────────

class TestStoreSecretKeyringUnavailable:
    """store_secret() con KEYRING_AVAILABLE=False → False."""

    def test_returns_false(self):
        with patch("src.utils.secrets_manager.KEYRING_AVAILABLE", False):
            result = store_secret("KEY", "val")
        assert result is False


# ── store_secret — Exception path ──────────────────────────────────────────

class TestStoreSecretException:
    """store_secret() cuando keyring.set_password lanza excepción."""

    def test_returns_false_on_error(self):
        _fake_keyring.set_password.side_effect = Exception("fail")
        result = store_secret("CAPTCHA_API_KEY", "val")
        assert result is False


# ── store_all ──────────────────────────────────────────────────────────────

class TestStoreAll:
    """store_all() — migración masiva de secrets a keyring."""

    def test_migrates_real_values(self):
        env_vals = {"CAPTCHA_API_KEY": "real_captcha", "STORAGE_KEY": "real_stg"}
        with patch.dict(os.environ, env_vals, clear=True):
            store_all()
        calls = _fake_keyring.set_password.call_args_list
        assert len(calls) == 2
        _fake_keyring.set_password.assert_any_call(
            "agente-tramites-gobmx", "CAPTCHA_API_KEY", "real_captcha"
        )
        _fake_keyring.set_password.assert_any_call(
            "agente-tramites-gobmx", "STORAGE_KEY", "real_stg"
        )

    def test_skips_placeholder_values(self):
        env_vals = {
            "CAPTCHA_API_KEY": "tu_api_key_aqui",
            "STORAGE_KEY": "cambia_esta_clave_secreta_32chars!",
        }
        with patch.dict(os.environ, env_vals, clear=True):
            store_all()
        assert _fake_keyring.set_password.call_count == 0

    def test_skips_empty_values(self):
        with patch.dict(os.environ, {}, clear=True):
            store_all()
        assert _fake_keyring.set_password.call_count == 0

    def test_mixed_values(self, capsys):
        """Solo las vars con valor real se migran; placeholders/empty no."""
        env_vals = {
            "CAPTCHA_API_KEY": "real_captcha",
            "IMAP_EMAIL": "real@email.com",
            "IMAP_PASSWORD": "real_pass",
            "STORAGE_KEY": "",                     # empty → skip
            "ANTHROPIC_API_KEY": "tu_api_key_aqui",  # placeholder → skip
        }
        with patch.dict(os.environ, env_vals, clear=True):
            store_all()
        out, _ = capsys.readouterr()
        assert "3/5" in out
        assert _fake_keyring.set_password.call_count == 3


# ── main_cli ───────────────────────────────────────────────────────────────

class TestMainCli:
    """main_cli() — CLI interactivo."""

    # ── store-all ──────────────────────────────────────────────────────

    def test_action_store_all(self, capsys):
        with patch.object(sys, "argv", ["secrets_manager.py", "store-all"]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "Migrando" in out

    # ── list ────────────────────────────────────────────────────────────

    def test_action_list_with_values(self, capsys):
        _fake_keyring.get_password.return_value = "supersecret"
        with patch.object(sys, "argv", ["secrets_manager.py", "list"]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "CAPTCHA_API_KEY" in out
        assert "supe" in out  # first 4 chars of masked value

    def test_action_list_no_values(self, capsys):
        _fake_keyring.get_password.return_value = None
        with patch.object(sys, "argv", ["secrets_manager.py", "list"]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "no configurado" in out

    def test_action_list_keyring_unavailable(self, capsys):
        with patch.object(sys, "argv", ["secrets_manager.py", "list"]), \
             patch("src.utils.secrets_manager.KEYRING_AVAILABLE", False):
            main_cli()
        out, _ = capsys.readouterr()
        assert "keyring no disponible" in out

    # ── delete ──────────────────────────────────────────────────────────

    def test_action_delete(self, capsys):
        with patch.object(sys, "argv",
                          ["secrets_manager.py", "delete", "--key", "CAPTCHA_API_KEY"]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "eliminado" in out
        _fake_keyring.delete_password.assert_called_once_with(
            "agente-tramites-gobmx", "CAPTCHA_API_KEY"
        )

    def test_action_delete_missing_key(self, capsys):
        with patch.object(sys, "argv", ["secrets_manager.py", "delete"]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "Especificá --key" in out

    def test_action_delete_keyring_unavailable(self, capsys):
        with patch.object(sys, "argv",
                          ["secrets_manager.py", "delete", "--key", "KEY"]), \
             patch("src.utils.secrets_manager.KEYRING_AVAILABLE", False):
            main_cli()
        out, _ = capsys.readouterr()
        assert "keyring no disponible" in out

    def test_action_delete_error(self, capsys):
        """Exception en delete_password se captura y muestra."""
        _fake_keyring.delete_password.side_effect = Exception("not found")
        with patch.object(sys, "argv",
                          ["secrets_manager.py", "delete", "--key", "CAPTCHA_API_KEY"]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "not found" in out

    # ── store (individual) ──────────────────────────────────────────────

    def test_action_store_with_value(self, capsys):
        with patch.object(sys, "argv", [
                "secrets_manager.py", "store",
                "--key", "CAPTCHA_API_KEY", "--value", "new_val",
        ]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "✅" in out
        _fake_keyring.set_password.assert_called_once_with(
            "agente-tramites-gobmx", "CAPTCHA_API_KEY", "new_val"
        )

    def test_action_store_missing_key(self, capsys):
        with patch.object(sys, "argv", ["secrets_manager.py", "store"]):
            main_cli()
        out, _ = capsys.readouterr()
        assert "Especificá --key" in out

    def test_action_store_with_input_fallback(self, capsys):
        """Sin --value, lee de input()."""
        with patch("builtins.input", return_value="from_input"):
            with patch.object(sys, "argv", [
                    "secrets_manager.py", "store",
                    "--key", "CAPTCHA_API_KEY",
            ]):
                main_cli()
        out, _ = capsys.readouterr()
        assert "✅" in out
        _fake_keyring.set_password.assert_called_once_with(
            "agente-tramites-gobmx", "CAPTCHA_API_KEY", "from_input"
        )


def teardown_module(module=None):
    """Detiene los patches para no contaminar otros tests."""
    for p in reversed(_patches):
        p.stop()
