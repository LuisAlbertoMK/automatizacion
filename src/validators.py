"""
validators.py
Validación de formatos mexicanos: CURP, RFC, email.
Todas las funciones retornan el valor normalizado o lanzan ValueError.
"""

import re

# ── Expresiones regulares ────────────────────────────────────────────

CURP_RE = re.compile(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9][0-9A-H]$")

# RFC: persona física (13 chars: 4 letras + 6 dígitos + 3 alfanum)
#      persona moral  (12 chars: 3 letras  + 6 dígitos + 3 alfanum)
RFC_RE = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")

# Email: formato básico RFC 5322 (sin dobles puntos en dominio)
EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$"
)


# ── Validadores ───────────────────────────────────────────────────────

def _calcular_digito_verificador(curp17: str) -> str:
    pesos = [18, 20, 11, 19, 16, 23, 20, 11, 22, 15, 17, 20, 12, 17, 18, 15, 14, 19]
    suma = 0
    for i, ch in enumerate(curp17):
        if ch.isdigit():
            valor = int(ch)
        else:
            valor = ord(ch) - 55  # A=10, B=11, ..., Z=35
        suma += valor * pesos[i]
    residuo = suma % 18
    if residuo < 10:
        return str(residuo)
    return chr(residuo + 55)  # 10=A, 11=B, ..., 17=H


def validar_curp(curp: str) -> str:
    """Valida y normaliza una CURP. Retorna en mayúsculas."""
    c = curp.strip().upper()
    if not CURP_RE.match(c):
        masked = curp[:4] + "****" + curp[-2:] if len(curp) >= 6 else "****"
        raise ValueError(
            f"CURP inválida: formato no reconocido ({masked}). "
            "Debe tener 18 caracteres alfanuméricos (ej: GODE561231HDFLRN03)"
        )
    esperado = _calcular_digito_verificador(c[:17])
    if c[17] != esperado:
        raise ValueError(
            f"CURP inválida: dígito verificador '{c[17]}' no coincide "
            f"(esperado '{esperado}'). Verifique los datos de la CURP."
        )
    return c


def validar_rfc(rfc: str) -> str:
    """Valida y normaliza un RFC. Retorna en mayúsculas."""
    r = rfc.strip().upper()
    if not RFC_RE.match(r):
        masked = rfc[:3] + "****" if len(rfc) >= 3 else "****"
        raise ValueError(
            f"RFC inválido: formato no reconocido ({masked}). "
            "Debe tener 12-13 caracteres (ej: GODE561231KL7)"
        )
    return r


def validar_email(email: str) -> str:
    """Valida y normaliza un email. Retorna en minúsculas."""
    e = email.strip().lower()
    if not EMAIL_RE.match(e):
        parts = email.split("@")
        masked = parts[0][:2] + "***@" + parts[1] if len(parts) == 2 else "***"
        raise ValueError(f"Email inválido: formato no reconocido ({masked})")
    return e
