"""Tests para exceptions.py — jerarquía unificada de errores."""


import pytest

from src.exceptions import (  # noqa: E402
    AntecedentesError,
    CaptchaError,
    CURPError,
    FreeCaptchaError,
    MailReaderError,
    ModuleError,
    NSSError,
    OCRError,
    StorageError,
    TenenciaError,
    TramiteError,
    VoiceInputError,
)


class TestTramiteError:
    def test_base_exception_is_exception_subclass(self):
        assert issubclass(TramiteError, Exception)

    def test_base_with_message(self):
        err = TramiteError("algo salió mal")
        assert str(err) == "algo salió mal"
        assert err.module == ""

    def test_base_with_module(self):
        err = TramiteError("error en curp", module="curp")
        assert str(err) == "error en curp"
        assert err.module == "curp"


HIERARCHY: list[tuple[type, type]] = [
    (CaptchaError, TramiteError),
    (FreeCaptchaError, CaptchaError),
    (OCRError, TramiteError),
    (MailReaderError, TramiteError),
    (VoiceInputError, TramiteError),
    (ModuleError, TramiteError),
    (CURPError, ModuleError),
    (NSSError, ModuleError),
    (TenenciaError, ModuleError),
    (AntecedentesError, ModuleError),
    (StorageError, TramiteError),
]


class TestExceptionHierarchy:
    @pytest.mark.parametrize("exc_class,parent", HIERARCHY)
    def test_inheritance(self, exc_class, parent):
        assert issubclass(exc_class, parent)

    @pytest.mark.parametrize("exc_class,_", HIERARCHY)
    def test_instantiation(self, exc_class, _):
        err = exc_class("test error")
        assert str(err) == "test error"

    @pytest.mark.parametrize("exc_class,_", HIERARCHY)
    def test_isinstance_check(self, exc_class, _):
        err = exc_class("test")
        assert isinstance(err, TramiteError)

    def test_all_exceptions_raised_correctly(self):
        """Verify each exc type can be raised/caught by its parent."""
        for exc_class, parent in HIERARCHY:
            try:
                raise exc_class("raised")
            except parent:
                pass  # expected
            except Exception:  # noqa: E722
                pytest.fail(f"{exc_class.__name__} not caught by {parent.__name__}")
