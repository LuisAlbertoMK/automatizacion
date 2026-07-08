"""
validators.py
Validación de formatos mexicanos: CURP, RFC, email.
Todas las funciones retornan el valor normalizado o lanzan ValueError.
"""

import re

# ── Expresiones regulares ────────────────────────────────────────────

CURP_RE = re.compile(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$")

# RFC: persona física (13 chars: 4 letras + 6 dígitos + 3 alfanum)
#      persona moral  (12 chars: 3 letras  + 6 dígitos + 3 alfanum)
RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")

# Email: formato básico RFC 5322
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


# ── Validadores ───────────────────────────────────────────────────────

def validar_curp(curp: str) -> str:
    """Valida y normaliza una CURP. Retorna en mayúsculas."""
    c = curp.strip().upper()
    if not CURP_RE.match(c):
        raise ValueError(
            f"CURP inválida: '{curp}'. Debe tener 18 caracteres alfanuméricos "
            "(ej: GODE561231HDFLRN03)"
        )
    return c


def validar_rfc(rfc: str) -> str:
    """Valida y normaliza un RFC. Retorna en mayúsculas."""
    r = rfc.strip().upper()
    if not RFC_RE.match(r):
        raise ValueError(
            f"RFC inválido: '{rfc}'. Debe tener 12-13 caracteres "
            "(ej: GODE561231KL7)"
        )
    return r


def validar_email(email: str) -> str:
    """Valida y normaliza un email. Retorna en minúsculas."""
    e = email.strip().lower()
    if not EMAIL_RE.match(e):
        raise ValueError(f"Email inválido: '{email}'")
    return e
