"""Tests unitarios para utils/storage.py — encriptacion y perfiles."""

import os
import sys

import pytest

os.environ["STORAGE_KEY"] = "test-key-32-chars-for-aes!xx"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from exceptions import StorageError  # noqa: E402
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


def test_get_cipher_no_key():
    """Line 34: _get_cipher() sin STORAGE_KEY debe levantar StorageError."""
    # Usar un flag para saber si estamos en el test
    # Para evitar recargar el módulo, simplemente parcheamos os.getenv
    import os as os_mod

    from utils.storage import _get_cipher

    original_getenv = os_mod.getenv

    def mock_getenv(key, default=None):
        if key == "STORAGE_KEY":
            return None
        return original_getenv(key, default)

    os_mod.getenv = mock_getenv
    try:
        with pytest.raises(StorageError, match="STORAGE_KEY no configurada"):
            _get_cipher()
    finally:
        os_mod.getenv = original_getenv


def test_load_all_no_file():
    """Line 47: _load_all() cuando DATA_FILE no existe retorna {}."""
    from utils.storage import DATA_FILE, _load_all

    if DATA_FILE.exists():
        DATA_FILE.unlink()
    assert _load_all() == {}


def test_hash_sensitive_field():
    """Lines 73-76: _hash_sensitive hashea campos sensibles."""
    from utils.storage import _hash_sensitive, load_profile, save_profile

    # Verificar que un campo sensible se hashea (no aparece en texto claro)
    profile = {"nombre": "Juan", "password": "secreta123", "correo": "j@j.com"}
    hashed = _hash_sensitive(profile, "_test_sens")
    assert "password" not in hashed
    assert "_password_hash" in hashed
    assert "_password_salt" in hashed
    assert hashed["nombre"] == "Juan"
    assert hashed["correo"] == "j@j.com"

    # Verificar round-trip: save + load omite campos hash
    save_profile("_test_sens", profile)
    loaded = load_profile("_test_sens")
    assert loaded["nombre"] == "Juan"
    assert loaded["correo"] == "j@j.com"
    assert "password" not in loaded
    assert not any(k.startswith("_") for k in loaded)


class TestVerifySensitive:
    """Lines 102-113: verify_sensitive() en sus 3 ramas."""

    def test_verify_correct(self):
        from utils.storage import save_profile, verify_sensitive

        save_profile("_test_vs", {"password": "mypass"})
        assert verify_sensitive("_test_vs", "password", "mypass") is True

    def test_verify_wrong(self):
        from utils.storage import save_profile, verify_sensitive

        save_profile("_test_vs2", {"password": "correct"})
        assert verify_sensitive("_test_vs2", "password", "wrong") is False

    def test_verify_no_profile(self):
        from utils.storage import verify_sensitive

        assert verify_sensitive("_test_noexiste", "password", "x") is False

    def test_verify_no_hash_stored_returns_true(self):
        """Si el campo no tiene hash guardado, asume válido (True)."""
        from utils.storage import save_profile, verify_sensitive

        # Guardar perfil SIN campos sensibles
        save_profile("_test_nohash", {"curp": "ABC123"})
        # verify_sensitive sobre campo que nunca se guardó con hash
        assert verify_sensitive("_test_nohash", "password", "anything") is True


class TestDeleteProfile:
    """Lines 123-128: delete_profile() True/False."""

    def test_delete_existing(self):
        from utils.storage import delete_profile, load_profile, save_profile

        save_profile("_test_del", {"curp": "DEL"})
        assert load_profile("_test_del") is not None
        assert delete_profile("_test_del") is True
        assert load_profile("_test_del") is None

    def test_delete_nonexistent(self):
        from utils.storage import delete_profile

        assert delete_profile("_test_no_del") is False


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
