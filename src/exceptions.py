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


class RFCError(ModuleError):
    """Error en módulo RFC SAT."""
    pass


class ActaNacimientoError(ModuleError):
    """Error en módulo Acta de Nacimiento."""
    pass


class PasaporteError(ModuleError):
    """Error en módulo Cita Pasaporte SRE."""
    pass


class SemanasError(ModuleError):
    """Error en módulo Semanas Cotizadas IMSS."""
    pass


class ControlConfianzaError(ModuleError):
    """Error en módulo Control de Confianza."""
    pass


class BuroError(ModuleError):
    """Error en módulo Buró de Crédito."""
    pass


class CirculoError(ModuleError):
    """Error en módulo Círculo de Crédito."""
    pass


class CitaINEerror(ModuleError):
    """Error en módulo Cita INE."""
    pass


class CitaSATError(ModuleError):
    """Error en módulo Cita SAT."""
    pass


# ── Documentos / IA ───────────────────────────────────────────────────────

class DocumentoError(TramiteError):
    """Error base en generación de documentos."""
    pass


class CVError(DocumentoError):
    """Error en generación de CV."""
    pass


class EscritoError(DocumentoError):
    """Error en generación de escritos."""
    pass


class ClaudeError(TramiteError):
    """Error en llamada a Anthropic Claude API."""
    pass


# ── Almacenamiento ─────────────────────────────────────────────────────────

class StorageError(TramiteError):
    """Error en almacenamiento de perfiles."""
    pass
