"""Tests unitarios para utils/storage.py — encriptacion y perfiles."""

import os
import sys

import pytest

os.environ["STORAGE_KEY"] = "test-key-32-chars-for-aes!xx"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.storage import (  # noqa: E402
    DATA_FILE,
    _save_all,  # noqa: E402
    list_profiles,
    load_profile,
    save_profile,
)


@pytest.fixture(autouse=True)
def clean_data():
    """Resetea el archivo de datos antes de cada test."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _save_all({})
    yield


class TestStorage:
    def test_save_and_load(self):
        profile = {"curp": "TEST123456", "correo": "test@test.com"}
        save_profile("_test_alice", profile)
        assert load_profile("_test_alice") == profile

    def test_load_nonexistent(self):
        assert load_profile("_test_no_existe") is None

    def test_list_profiles(self):
        save_profile("_test_bob", {"curp": "BOB123456"})
        assert "_test_bob" in list_profiles()

    def test_overwrite_profile(self):
        save_profile("_test_over", {"curp": "OLD"})
        save_profile("_test_over", {"curp": "NEW"})
        assert load_profile("_test_over")["curp"] == "NEW"

    def test_encryption_nonce_differs(self):
        """Mismos datos producen ciphertext diferente (nonce aleatorio)."""
        profile = {"curp": "SAME"}
        save_profile("_test_enc", profile)
        c1 = DATA_FILE.read_bytes()
        save_profile("_test_enc", profile)
        c2 = DATA_FILE.read_bytes()
        assert c1 != c2, "Ciphertext debe diferir por nonce aleatorio"

    def test_tamper_returns_none_gracefully(self):
        """Corromper ciphertext retorna None graceful (no crash)."""
        save_profile("_test_tamper", {"curp": "OK"})
        data = bytearray(DATA_FILE.read_bytes())
        data[len(data) // 2] ^= 0xFF
        DATA_FILE.write_bytes(bytes(data))
        # Debe retornar None graceful, no crashear
        result = load_profile("_test_tamper")
        assert result is None
