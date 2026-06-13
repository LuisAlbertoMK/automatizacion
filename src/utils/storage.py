"""
utils/storage.py
Almacenamiento local de perfiles de clientes, encriptado con Fernet.
Los datos NUNCA salen de tu PC.

Estructura de un perfil:
{
    "nombre": "Juan García López",
    "curp": "GALJ800101HDFXXXX00",
    "correo": "juan@gmail.com",
    "placa": "ABC1234",
    "rfc": "GALJ800101XXX",
    "notas": "Cliente frecuente"
}
"""

import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from exceptions import StorageError

DATA_FILE = Path(os.getenv("OUTPUT_DIR", "./data")) / "perfiles.json"


def _get_cipher() -> Fernet:
    """Deriva una clave Fernet desde STORAGE_KEY del .env"""
    raw_key = os.getenv("STORAGE_KEY")
    if not raw_key:
        raise StorageError(
            "STORAGE_KEY no configurada en config.env. "
            "Generá una con: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    # SHA-256 -> 32 bytes -> base64url para Fernet
    hashed = hashlib.sha256(raw_key.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(hashed)
    return Fernet(fernet_key)


def _load_all() -> dict:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        return {}
    try:
        cipher = _get_cipher()
        encrypted = DATA_FILE.read_bytes()
        decrypted = cipher.decrypt(encrypted)
        return json.loads(decrypted)
    except (InvalidToken, json.JSONDecodeError):
        return {}


def _save_all(data: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    cipher = _get_cipher()
    raw = json.dumps(data, ensure_ascii=False, indent=2).encode()
    encrypted = cipher.encrypt(raw)
    DATA_FILE.write_bytes(encrypted)


SENSITIVE_FIELDS = {"password", "secret", "token", "api_key", "imap_password"}


def _hash_sensitive(profile: dict, alias: str = "") -> dict:
    """Hashea campos sensibles dentro del perfil usando alias como salt."""
    safe = {}
    for k, v in profile.items():
        if isinstance(v, str) and any(s in k.lower() for s in SENSITIVE_FIELDS):
            salt = hashlib.sha256(alias.encode()).hexdigest()[:16]
            hashed = hashlib.pbkdf2_hmac("sha256", v.encode(), salt.encode(), 100_000)
            safe[f"_{k}_hash"] = base64.urlsafe_b64encode(hashed).decode()
            safe[f"_{k}_salt"] = salt
        else:
            safe[k] = v
    return safe


def save_profile(alias: str, profile: dict):
    """Guarda o actualiza un perfil (con hasheo de campos sensibles)."""
    all_profiles = _load_all()
    all_profiles[alias] = _hash_sensitive(profile, alias)
    _save_all(all_profiles)
    print(f"  [storage] Perfil '{alias}' guardado [OK]")


def load_profile(alias: str) -> dict | None:
    """Carga un perfil por alias. Retorna None si no existe."""
    all_profiles = _load_all()
    profile = all_profiles.get(alias)
    if profile is None:
        return None
    # Devolver copia sin los campos hash internos
    return {k: v for k, v in profile.items() if not k.startswith("_")}


def verify_sensitive(alias: str, field: str, value: str) -> bool:
    """Verifica un campo sensible contra el hash guardado."""
    all_profiles = _load_all()
    profile = all_profiles.get(alias)
    if not profile:
        return False
    hash_key = f"_{field}_hash"
    salt_key = f"_{field}_salt"
    stored_hash = profile.get(hash_key)
    salt = profile.get(salt_key)
    if not stored_hash or not salt:
        return True  # No hay hash previo, asumir válido
    check = hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 100_000)
    return base64.urlsafe_b64encode(check).decode() == stored_hash


def list_profiles() -> list[str]:
    """Lista todos los alias de perfiles guardados."""
    return list(_load_all().keys())


def delete_profile(alias: str) -> bool:
    """Elimina un perfil. Retorna True si existía."""
    all_profiles = _load_all()
    if alias in all_profiles:
        del all_profiles[alias]
        _save_all(all_profiles)
        return True
    return False
