"""Configuración global de tests — baja rondas bcrypt para velocidad."""
import os

# Reducir rondas bcrypt.kdf para tests (evita timeouts)
os.environ.setdefault("BCRYPT_KDF_ROUNDS", "16")
os.environ.setdefault("BCRYPT_HASH_ROUNDS", "8")
