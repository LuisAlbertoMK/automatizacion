"""Tests unitarios para validators.py — CURP, RFC, email."""

import pytest

from src.validators import validar_curp, validar_email, validar_rfc


class TestValidarCurp:
    """validar_curp(): 18 chars, formato mexicano."""

    # ── Válidos ────────────────────────────────────────────────────
    @pytest.mark.parametrize("input_curp,expected", [
        ("GODE561231HDFLRN03", "GODE561231HDFLRN03"),
        ("  xema920217hnlslr07  ", "XEMA920217HNLSLR07"),       # strip
        ("MARS950101MDFLRN09", "MARS950101MDFLRN09"),
        ("gode561231hdflrn03", "GODE561231HDFLRN03"),           # lower→upper
    ])
    def test_curp_valida(self, input_curp, expected):
        assert validar_curp(input_curp) == expected

    # ── Inválidos ──────────────────────────────────────────────────
    @pytest.mark.parametrize("bad_curp", [
        "",                       # vacío
        "GODE561231",             # muy corto
        "GODE561231HDFLRN03X",    # muy largo
        "GODE56123XHDFLRN03",     # letra en posición numérica
        "123456789012345678",     # solo dígitos
        "GODE561231HDFLRN0$",     # caracter especial
    ])
    def test_curp_invalida(self, bad_curp):
        with pytest.raises(ValueError, match="CURP inválida"):
            validar_curp(bad_curp)


class TestValidarRfc:
    """validar_rfc(): 12-13 chars, física (13) o moral (12)."""

    # ── Válidos ────────────────────────────────────────────────────
    @pytest.mark.parametrize("input_rfc,expected", [
        ("GODE561231KL7", "GODE561231KL7"),   # física 13 chars
        ("  abc123456kl7  ", "ABC123456KL7"), # strip + upper
        ("AAA010101AAA", "AAA010101AAA"),     # moral 12 chars
        ("ÑÑÑ010101AAA", "ÑÑÑ010101AAA"),    # Ñ permitida
        ("&AB010101AAA", "&AB010101AAA"),     # & permitida en moral
    ])
    def test_rfc_valido(self, input_rfc, expected):
        assert validar_rfc(input_rfc) == expected

    # ── Inválidos ──────────────────────────────────────────────────
    @pytest.mark.parametrize("bad_rfc", [
        "",                       # vacío
        "GODE561231",             # muy corto
        "GODE561231KL712",        # muy largo
        "123456789012",           # solo dígitos
        "GODE-61231KL7",          # caracter especial
        "abc",                    # completamente inválido
    ])
    def test_rfc_invalido(self, bad_rfc):
        with pytest.raises(ValueError, match="RFC inválido"):
            validar_rfc(bad_rfc)


class TestValidarEmail:
    """validar_email(): formato RFC 5322 básico."""

    # ── Válidos ────────────────────────────────────────────────────
    @pytest.mark.parametrize("input_email,expected", [
        ("user@example.com", "user@example.com"),
        ("  USER@Example.COM  ", "user@example.com"),  # strip + lower
        ("a.b+c@sub.domain.co", "a.b+c@sub.domain.co"),
        ("user+tag@domain.com.mx", "user+tag@domain.com.mx"),
    ])
    def test_email_valido(self, input_email, expected):
        assert validar_email(input_email) == expected

    # ── Inválidos ──────────────────────────────────────────────────
    @pytest.mark.parametrize("bad_email", [
        "",                     # vacío
        "user",                 # sin @
        "@domain.com",          # sin local
        "user@",                # sin dominio
        "user@.com",            # dominio inválido
        "user@domain",          # sin TLD
        "user name@domain.com", # espacio en local
        "user@domain..com",     # doble punto es inválido
    ])
    def test_email_invalido(self, bad_email):
        with pytest.raises(ValueError, match="Email inválido"):
            validar_email(bad_email)
