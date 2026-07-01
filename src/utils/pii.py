"""
utils/pii.py
Sanitización de datos personales (PII) para evitar fugas a stdout/logs.
"""

import re
from typing import Any


def sanitize_curp(curp: str) -> str:
    """Muestra solo los primeros 4 caracteres de una CURP."""
    if not curp or len(curp) < 4:
        return "****"
    return f"{curp[:4]}****"


def sanitize_nss(nss: str) -> str:
    """Muestra solo los primeros 5 dígitos de un NSS."""
    if not nss or len(nss) < 5:
        return "******"
    return f"{nss[:5]}******"


def sanitize_email(email: str) -> str:
    """Muestra solo la primera letra + dominio del email."""
    if not email or "@" not in email:
        return "***@***"
    local, domain = email.split("@", 1)
    if len(local) < 1:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def sanitize_pii(value: Any, pii_type: str | None = None) -> str:
    """Sanitiza un valor según su tipo PII.

    Args:
        value: El valor a sanitizar.
        pii_type: Tipo de PII — "curp", "nss", "email", o None para auto-detectar.

    Returns:
        Cadena sanitizada.
    """
    text = str(value)
    if pii_type:
        return globals()[f"sanitize_{pii_type}"](text)

    # Auto-detección por formato
    if re.match(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$", text):
        return sanitize_curp(text)
    if re.match(r"^\d{11}$", text):
        return sanitize_nss(text)
    if "@" in text and "." in text:
        return sanitize_email(text)
    return text
