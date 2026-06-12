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

import os
import json
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
import base64
import hashlib


DATA_FILE = Path(os.getenv("OUTPUT_DIR", "./data")) / "perfiles.json"


def _get_cipher() -> Fernet:
    """Deriva una clave Fernet desde STORAGE_KEY del .env"""
    raw_key = os.getenv("STORAGE_KEY")
    if not raw_key:
        raise ValueError(
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


def save_profile(alias: str, profile: dict):
    """Guarda o actualiza un perfil."""
    all_profiles = _load_all()
    all_profiles[alias] = profile
    _save_all(all_profiles)
    print(f"  [storage] Perfil '{alias}' guardado [OK]")


def load_profile(alias: str) -> dict | None:
    """Carga un perfil por alias. Retorna None si no existe."""
    all_profiles = _load_all()
    return all_profiles.get(alias)


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
