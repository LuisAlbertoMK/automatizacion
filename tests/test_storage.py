"""Tests unitarios para utils/storage.py — encriptacion y perfiles."""

import base64
import hashlib
import json
import os
import secrets
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

# Se necesita en collection por los imports internos de storage.py
os.environ["STORAGE_KEY"] = "test-key-32-chars-for-aes!xx"

from src.exceptions import StorageError  # noqa: E402
from src.utils.storage import (  # noqa: E402
    DATA_FILE,
    SALT_FILE,
    _get_cipher,
    _get_salt,
    _load_all,
    _save_all,  # noqa: E402
    list_profiles,
    load_profile,
    save_profile,
    storage_migrate_salt,
)


@pytest.fixture(autouse=True)
def clean_data():
    """Resetea el archivo de datos antes de cada test."""
    # Algunos tests del suite limpian os.environ via patch.dict(clear=True)
    # Re-establecer STORAGE_KEY dentro del fixture asegura compatibilidad
    if not os.getenv("STORAGE_KEY"):
        os.environ["STORAGE_KEY"] = "test-key-32-chars-for-aes!xx"
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    _save_all({})
    yield


def test_get_cipher_no_key():
    """Line 34: _get_cipher() sin STORAGE_KEY debe levantar StorageError."""
    # Usar un flag para saber si estamos en el test
    # Para evitar recargar el módulo, simplemente parcheamos os.getenv
    import os as os_mod


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
    from src.utils.storage import DATA_FILE, _load_all

    if DATA_FILE.exists():
        DATA_FILE.unlink()
    assert _load_all() == {}


def test_hash_sensitive_field():
    """Lines 73-76: _hash_sensitive hashea campos sensibles."""
    from src.utils.storage import _hash_sensitive, load_profile, save_profile

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
        from src.utils.storage import save_profile, verify_sensitive

        save_profile("_test_vs", {"password": "mypass"})
        assert verify_sensitive("_test_vs", "password", "mypass") is True

    def test_verify_wrong(self):
        from src.utils.storage import save_profile, verify_sensitive

        save_profile("_test_vs2", {"password": "correct"})
        assert verify_sensitive("_test_vs2", "password", "wrong") is False

    def test_verify_no_profile(self):
        from src.utils.storage import verify_sensitive

        assert verify_sensitive("_test_noexiste", "password", "x") is False

    def test_verify_no_hash_stored_returns_true(self):
        """Si el campo no tiene hash guardado, asume válido (True)."""
        from src.utils.storage import save_profile, verify_sensitive

        # Guardar perfil SIN campos sensibles
        save_profile("_test_nohash", {"curp": "ABC123"})
        # verify_sensitive sobre campo que nunca se guardó con hash
        assert verify_sensitive("_test_nohash", "password", "anything") is True


class TestRandomSalt:
    """M6: salt aleatorio por campo (no determinístico)."""

    def test_salt_is_not_deterministic(self):
        """Dos llamadas con el mismo alias producen salts diferentes."""
        from src.utils.storage import _hash_sensitive

        profile = {"password": "secret123"}
        h1 = _hash_sensitive(profile, "_test_salt1")
        h2 = _hash_sensitive(profile, "_test_salt1")
        assert h1["_password_salt"] != h2["_password_salt"]

    def test_verify_works_with_random_salt(self):
        """verify_sensitive funciona con salt aleatorio."""
        from src.utils.storage import save_profile, verify_sensitive

        save_profile("_test_rs", {"api_key": "key123"})
        assert verify_sensitive("_test_rs", "api_key", "key123") is True
        assert verify_sensitive("_test_rs", "api_key", "wrong") is False

    def test_salt_is_hex_16_chars(self):
        """El salt es un hex string de 16 chars."""
        from src.utils.storage import _hash_sensitive

        h = _hash_sensitive({"password": "x"}, "_test_fmt")
        salt = h["_password_salt"]
        assert len(salt) == 16
        int(salt, 16)  # parseable como hex

    def test_is_deterministic_salt_detects_old(self):
        """_is_deterministic_salt detecta sha256(alias)[:16]."""
        from src.utils.storage import _is_deterministic_salt

        alias = "_test_det"
        old_salt = hashlib.sha256(alias.encode()).hexdigest()[:16]
        assert _is_deterministic_salt(old_salt, alias) is True

    def test_is_deterministic_salt_random_is_false(self):
        """Salt aleatorio no es detectado como deterministic."""
        from src.utils.storage import _is_deterministic_salt

        assert _is_deterministic_salt(secrets.token_hex(16)[:16], "_any") is False

    def test_storage_needs_migration_detected(self):
        """storage_needs_migration detecta salt determinístico en profile."""
        from src.utils.storage import storage_needs_migration

        alias = "_test_mig"
        old_salt = hashlib.sha256(alias.encode()).hexdigest()[:16]
        with patch("src.utils.storage._load_all") as mock_load:
            mock_load.return_value = {
                alias: {"_password_hash": "abc", "_password_salt": old_salt}
            }
            assert storage_needs_migration(alias) is True

    def test_storage_needs_migraton_false_for_random_salt(self):
        """storage_needs_migration retorna False para salt aleatorio."""
        from src.utils.storage import _save_all, storage_needs_migration

        alias = "_test_nm"
        _save_all({alias: {"_password_salt": secrets.token_hex(16)[:16]}})
        assert storage_needs_migration(alias) is False

    def test_storage_needs_migraton_false_nonexistent(self):
        """storage_needs_migration retorna False para perfil inexistente."""
        from src.utils.storage import storage_needs_migration
        assert storage_needs_migration("_noexiste_xyz") is False


class TestDeleteProfile:
    """Lines 123-128: delete_profile() True/False."""

    def test_delete_existing(self):
        from src.utils.storage import delete_profile, load_profile, save_profile

        save_profile("_test_del", {"curp": "DEL"})
        assert load_profile("_test_del") is not None
        assert delete_profile("_test_del") is True
        assert load_profile("_test_del") is None

    def test_delete_nonexistent(self):
        from src.utils.storage import delete_profile

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


# ── _get_salt ──────────────────────────────────────────────────────────────────

class TestGetSalt:
    """_get_salt() — generación de salt persistente (líneas 37-50)."""

    def test_creates_new_salt_when_missing(self):
        """Lines 47-50: genera y persiste salt de 16 bytes si no existe."""
        if SALT_FILE.exists():
            SALT_FILE.unlink()
        salt = _get_salt()
        assert SALT_FILE.exists()
        assert len(salt) == 16

    def test_returns_existing_salt(self):
        """Lines 45-46: retorna el salt existente."""
        assert SALT_FILE.exists()
        salt = _get_salt()
        assert len(salt) == 16


# ── storage_migrate_salt ───────────────────────────────────────────────────────

class TestStorageMigrateSalt:
    """storage_migrate_salt() — migración de salt legacy (líneas 160-191)."""

    @patch("src.utils.storage.os.getenv")
    def test_errors_without_storage_key(self, mock_getenv):
        """Line 167-168: levanta StorageError sin STORAGE_KEY."""
        mock_getenv.return_value = None
        with pytest.raises(StorageError, match="STORAGE_KEY no configurada"):
            storage_migrate_salt()

    def test_noop_when_data_file_missing(self):
        """Lines 176-177: retorna si no hay DATA_FILE."""
        if DATA_FILE.exists():
            DATA_FILE.unlink()
        if SALT_FILE.exists():
            SALT_FILE.unlink()
        storage_migrate_salt()  # No debe levantar excepción

    def test_noop_on_already_migrated(self):
        """Line 183-184: segunda llamada es no-op (InvalidToken catch)."""
        save_profile("_test_mig", {"curp": "MIG"})
        storage_migrate_salt()  # 1ra — migra (o es no-op si ya nuevo)
        storage_migrate_salt()  # 2da — catch InvalidToken → return

    def test_migrates_old_format(self):
        """Lines 170-191: migra datos cifrados con salt hardcodeado.
        
        NO elimina SALT_FILE antes — así cubre la línea 189
        (SALT_FILE.unlink() dentro de storage_migrate_salt).
        """
        # Crear datos con el salt VIEJO (b"fernet-key-salt", PBKDF2)
        raw_key = os.environ["STORAGE_KEY"]
        old_salt = b"fernet-key-salt"
        old_stretched = hashlib.pbkdf2_hmac("sha256", raw_key.encode(), old_salt, 600_000)
        old_cipher = Fernet(base64.urlsafe_b64encode(old_stretched))

        # Dejar SALT_FILE existente (lo creó clean_data) para cubrir línea 189
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        old_data = json.dumps(
            {"test_mig_profile": {"curp": "OLD"}}, ensure_ascii=False, indent=2
        ).encode()
        encrypted = old_cipher.encrypt(old_data)
        DATA_FILE.write_bytes(encrypted)

        # Migrar — SALT_FILE existe, pasa por línea 189
        storage_migrate_salt()

        # Verificar que los datos se leen con el nuevo salt
        data = _load_all()
        assert "test_mig_profile" in data
        assert data["test_mig_profile"]["curp"] == "OLD"


class TestGuardRounds:
    """Guardrail de seguridad — rounds bcrypt nunca por debajo del mínimo."""

    def test_defaults_no_inseguros(self):
        """Los rounds por defecto (sin env) deben ser >= 100 (sin UserWarning)."""
        import src.utils.storage as st

        assert st._KDF_ROUNDS >= st._MIN_BCRYPT_ROUNDS
        assert st._HASH_ROUNDS >= st._MIN_BCRYPT_ROUNDS

    def test_guard_rechaza_rounds_bajos(self):
        """Rounds < 100 deben levantar StorageError."""
        import src.utils.storage as st

        original_kdf, original_hash = st._KDF_ROUNDS, st._HASH_ROUNDS
        try:
            st._KDF_ROUNDS = 4
            st._HASH_ROUNDS = 4
            with pytest.raises(StorageError, match="mínimo seguro"):
                st._guard_rounds()
        finally:
            st._KDF_ROUNDS, st._HASH_ROUNDS = original_kdf, original_hash

    def test_guard_acepta_rounds_seguros(self):
        """Rounds >= 100 no levantan error."""
        import src.utils.storage as st

        st._guard_rounds()  # conftest los setea a 100 — no debe fallar
