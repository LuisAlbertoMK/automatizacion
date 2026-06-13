"""
exceptions.py — Jerarquía unificada de excepciones del Agente de Trámites.
Todas las excepciones del sistema heredan de TramiteError.
"""


class TramiteError(Exception):
    """Base de TODAS las excepciones del sistema."""
    def __init__(self, message: str, module: str = ""):
        self.module = module
        super().__init__(message)


# ── Captcha ────────────────────────────────────────────────────────────────

class CaptchaError(TramiteError):
    """Error del solver de captcha (2captcha o free)."""
    pass


class FreeCaptchaError(CaptchaError):
    """Error específico del FreeCaptchaSolver."""
    pass


# ── OCR ────────────────────────────────────────────────────────────────────

class OCRError(TramiteError):
    """Error en OCR."""
    pass


# ── Mail ───────────────────────────────────────────────────────────────────

class MailReaderError(TramiteError):
    """Error leyendo correo electrónico."""
    pass


# ── Voz ────────────────────────────────────────────────────────────────────

class VoiceInputError(TramiteError):
    """Error en entrada por voz."""
    pass


# ── Módulos de trámites ───────────────────────────────────────────────────

class ModuleError(TramiteError):
    """Error base para todos los módulos de trámites."""
    pass


class CURPError(ModuleError):
    """Error en módulo CURP."""
    pass


class NSSError(ModuleError):
    """Error en módulo NSS IMSS."""
    pass


class TenenciaError(ModuleError):
    """Error en módulo Tenencia."""
    pass


class AntecedentesError(ModuleError):
    """Error en módulo Antecedentes."""
    pass


# ── Almacenamiento ─────────────────────────────────────────────────────────

class StorageError(TramiteError):
    """Error en almacenamiento de perfiles."""
    pass
