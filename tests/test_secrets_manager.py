"""Tests para src/utils/secrets_manager.py — con keyring mockeado."""

from unittest.mock import patch, MagicMock
import os

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


def teardown_module(module=None):
    """Detiene los patches para no contaminar otros tests."""
    for p in reversed(_patches):
        p.stop()
