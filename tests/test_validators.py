"""Tests para src/validators.py — CURP, RFC, email."""

import pytest
from src.validators import (
    validar_curp,
    validar_rfc,
    validar_email,
    CURP_RE,
    RFC_RE,
    EMAIL_RE,
)


class TestCURP:
    VALIDAS = [
        "GODE561231HDFLRN03",
        "RAMS801231MDFLRN09",
        "HEGG660823HMNRRN05",
        "MARS850201MDFLRN00",
    ]
    INVALIDAS = [
        "",                    # vacía
        "ABC",                 # muy corta
        "GODE561231HDFLRN0",   # 17 caracteres
        "GODE561231HDFLRN031", # 19 caracteres
        "123456789012345678",  # solo dígitos
        "GODE561231HDFLRN0A",  # dígito verificador con letra
    ]

    def test_validas(self):
        for c in self.VALIDAS:
            assert validar_curp(c) == c

    def test_validas_minusculas(self):
        assert validar_curp("gode561231hdflrn03") == "GODE561231HDFLRN03"

    def test_validas_con_espacios(self):
        assert validar_curp("  GODE561231HDFLRN03  ") == "GODE561231HDFLRN03"

    def test_invalidas(self):
        for c in self.INVALIDAS:
            with pytest.raises(ValueError, match="CURP inv"):
                validar_curp(c)

    def test_regex_matches_valid(self):
        for c in self.VALIDAS:
            assert CURP_RE.match(c)

    def test_regex_rejects_invalid(self):
        for c in self.INVALIDAS:
            assert not CURP_RE.match(c)


class TestRFC:
    VALIDAS = [
        "GODE561231KL7",       # persona física (13)
        "RAMS801231ABC",       # persona física (13)
        "MARS850201XYZ",       # persona física (13)
        "AAA010101AAA",        # persona moral (12)
    ]
    INVALIDAS = [
        "",                    # vacía
        "ABC",                 # muy corta
        "GODE561231KL",        # 11 caracteres
        "GODE561231KL71",      # 14 caracteres
        "1234567890123",       # solo dígitos
    ]

    def test_validas(self):
        for r in self.VALIDAS:
            assert validar_rfc(r) == r

    def test_validas_minusculas(self):
        assert validar_rfc("gode561231kl7") == "GODE561231KL7"

    def test_invalidas(self):
        for r in self.INVALIDAS:
            with pytest.raises(ValueError, match="RFC inv"):
                validar_rfc(r)


class TestEmail:
    VALIDOS = [
        "a@b.com",
        "usuario@dominio.mx",
        "test@sub.dominio.org",
    ]
    INVALIDOS = [
        "",                    # vacío
        "invalido",            # sin @
        "@dominio.com",        # sin usuario
        "usuario@",            # sin dominio
        "usuario@dominio",     # sin TLD
        "a b@c.com",           # espacio en usuario
    ]

    def test_validos(self):
        for e in self.VALIDOS:
            assert validar_email(e) == e

    def test_validos_mayusculas(self):
        assert validar_email("User@Domain.COM") == "user@domain.com"

    def test_invalidos(self):
        for e in self.INVALIDOS:
            with pytest.raises(ValueError, match="Email inv"):
                validar_email(e)
