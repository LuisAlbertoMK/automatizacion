"""Tests para src/utils/pii.py — sanitización de datos sensibles."""

import pytest

from src.utils.pii import sanitize_curp, sanitize_nss, sanitize_email, sanitize_pii


class TestSanitizeCURP:
    def test_shows_first_4_chars_only(self):
        """CURP completa → primeros 4 + ****."""
        assert         sanitize_curp("GALJ800101HDFXXXX0") == "GALJ****"

    def test_short_string_returns_masked(self):
        assert sanitize_curp("ABC") == "****"

    def test_empty_returns_masked(self):
        assert sanitize_curp("") == "****"


class TestSanitizeNSS:
    def test_shows_first_5_digits(self):
        """NSS de 11 dígitos → primeros 5 + ******."""
        assert sanitize_nss("12345678901") == "12345******"

    def test_short_returns_masked(self):
        assert sanitize_nss("123") == "******"

    def test_empty_returns_masked(self):
        assert sanitize_nss("") == "******"


class TestSanitizeEmail:
    def test_shows_first_letter_and_domain(self):
        """Email → primera letra + ***@dominio."""
        assert sanitize_email("juan.perez@gmail.com") == "j***@gmail.com"

    def test_no_at_sign_returns_masked(self):
        assert sanitize_email("invalido") == "***@***"

    def test_empty_returns_masked(self):
        assert sanitize_email("") == "***@***"


class TestSanitizePII:
    def test_curp_type(self):
        result =         sanitize_pii("GALJ800101HDFXXXX0", "curp")
        assert result == "GALJ****"

    def test_email_type(self):
        result = sanitize_pii("test@example.com", "email")
        assert result == "t***@example.com"

    def test_unknown_type_raises_keyerror(self):
        """Si pii_type no existe como función sanitize_*, explota deliberadamente."""
        with pytest.raises(KeyError):
            sanitize_pii("valor secreto", "password")

    def test_auto_detects_curp(self):
        """Sin pii_type, detecta formato CURP (18 caracteres)."""
        result = sanitize_pii("GALJ800101HDFXXXX0")
        assert result == "GALJ****"

    def test_auto_detects_curp_18_chars_only(self):
        """No detecta CURP de 19+ caracteres."""
        result = sanitize_pii("GALJ800101HDFXXXX00")
        assert result == "GALJ800101HDFXXXX00"

    def test_auto_detects_nss(self):
        result = sanitize_pii("12345678901")
        assert result == "12345******"

    def test_auto_detects_email(self):
        result = sanitize_pii("test@example.com")
        assert result == "t***@example.com"

    def test_plain_text_returns_as_is(self):
        """Texto sin formato PII conocido se devuelve sin cambios."""
        assert sanitize_pii("hola mundo") == "hola mundo"
