"""
api.py — API REST para el Agente de Trámites GOB.MX.
Expone los trámites como endpoints HTTP con FastAPI.

Rate limiting via slowapi — configurable con vars de entorno:
    RATE_LIMIT_LIGHT     "30/minute"   (endpoints livianos: /, /health)
    RATE_LIMIT_CURP       "5/minute"   (consulta CURP)
    RATE_LIMIT_NSS        "5/minute"   (obtención NSS)
    RATE_LIMIT_PERFILES  "10/minute"   (perfiles)

Uso:
    uvicorn src.api:app --reload
    # o via docker: docker compose --profile api up
"""

import hmac
import os
import sys
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, FastAPI, HTTPException, Query, Request  # noqa: F401
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, field_validator
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from dotenv import load_dotenv

from src.exceptions import (
    CaptchaError,
    ClaudeError,
    DocumentoError,
    MailReaderError,
    ModuleError,
    OCRError,
    StorageError,
    TramiteError,
    VoiceInputError,
)
from src.utils.logger import get_logger

load_dotenv(Path(__file__).parent.parent / "config.env")
from src.utils.secrets_manager import init_secrets  # noqa: E402

init_secrets()

logger = get_logger("API")


if not FASTAPI_AVAILABLE:
    raise ImportError(
        "FastAPI no está instalado. Instalá con: pip install fastapi uvicorn"
    )


from src.tramites.curp import CURPModule  # noqa: E402
from src.tramites.nss import NSSModule  # noqa: E402
from src.utils.captcha import CaptchaSolver  # noqa: E402
from src.utils.storage import list_profiles, save_profile  # noqa: E402

# ── Rate limiting (slowapi) ─────────────────────────────────

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False
    logger.warning("slowapi no instalado — rate limiting desactivado")


def _rate_limit(key: str, default: str) -> str:
    """Lee una variable de entorno o devuelve el default para rate limit."""
    return os.getenv(f"RATE_LIMIT_{key}", default)


# ── Exception → HTTP code mapping ───────────────────────────

_EXCEPTION_STATUS_MAP: dict[type, int] = {
    CaptchaError: 409,        # Conflict — CAPTCHA needs manual solving
    OCRError: 422,            # Unprocessable — OCR failed to extract text
    MailReaderError: 502,     # Bad Gateway — mail service unreachable
    VoiceInputError: 422,     # Unprocessable — voice input failed
    DocumentoError: 422,      # Unprocessable — document generation failed
    ClaudeError: 502,         # Bad Gateway — AI service error
    StorageError: 500,        # Internal — profile storage error
    ModuleError: 502,         # Bad Gateway — government portal error
    TramiteError: 500,        # Internal — base system error
}

_EXCEPTION_DETAIL_MAP: dict[type, str] = {
    CaptchaError: "CAPTCHA no resuelto — intentá con 2captcha o resolvé manualmente",
    OCRError: "No se pudo extraer texto por OCR",
    MailReaderError: "Error al leer correo — verificá credenciales IMAP",
    VoiceInputError: "Error en entrada por voz",
    DocumentoError: "Error al generar documento",
    ClaudeError: "Servicio de IA no disponible — reintentá más tarde",
    ModuleError: "Error al consultar el portal gubernamental",
}


def _tramite_exception_to_http(exc: TramiteError) -> HTTPException:
    """Convierte una excepción del dominio a HTTPException con status code apropiado."""
    exc_type = type(exc)
    status = 500
    for cls in exc_type.__mro__:
        if cls in _EXCEPTION_STATUS_MAP:
            status = _EXCEPTION_STATUS_MAP[cls]
            break
    # Si es ModuleError (portal gubernamental) pero el mensaje indica input
    # del usuario, reasignar a 422 (Unprocessable) en vez de 502 (Bad Gateway).
    msg = str(exc)
    if isinstance(exc, ModuleError):
        _validation_hints = ("Se requiere", "inválido", "faltante", "rechazó el portal")
        if any(hint in msg for hint in _validation_hints):
            status = 422
    detail = msg or _EXCEPTION_DETAIL_MAP.get(exc_type, "Error interno del servidor")
    return HTTPException(status_code=status, detail=detail)


# ── Auth middleware ─────────────────────────────────────────

API_KEY = os.getenv("API_KEY", "")
PROD = os.getenv("PRODUCTION", "").lower() in ("1", "true", "yes")

if PROD and not API_KEY:
    logger.critical("API_KEY no configurada en producción — Abortando")
    sys.exit(1)

# Endpoints que NO requieren auth (health check, docs)
_PUBLIC_PATHS = frozenset({"/health", "/docs", "/redoc", "/openapi.json"})


async def _verify_api_key(request: Request, call_next):
    # Health check y docs siempre accesibles
    if request.url.path in _PUBLIC_PATHS:
        return await call_next(request)

    if not API_KEY:
        # Development: permitir pero registrar warning (1 vez)
        if not hasattr(_verify_api_key, "_warned"):
            logger.warning(
                "API_KEY no configurada — auth desactivado (solo desarrollo). "
                "Configurá API_KEY en config.env o Windows Credential Manager."
            )
            _verify_api_key._warned = True
        return await call_next(request)

    key = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(key, API_KEY):
        return JSONResponse(status_code=403, content={"detail": "API key inválida o faltante"})
    return await call_next(request)


# ── Models ─────────────────────────────────────────────────

class CurpRequest(BaseModel):
    curp: str
    perfil: Optional[str] = None

    @field_validator("curp")
    @classmethod
    def validar_curp(cls, v: str) -> str:
        from src.validators import validar_curp as _vc  # noqa: PLC0415
        return _vc(v)

class NssRequest(BaseModel):
    curp: str
    correo: str
    perfil: Optional[str] = None

    @field_validator("curp")
    @classmethod
    def validar_curp(cls, v: str) -> str:
        from src.validators import validar_curp as _vc  # noqa: PLC0415
        return _vc(v)

    @field_validator("correo")
    @classmethod
    def validar_correo(cls, v: str) -> str:
        from src.validators import validar_email as _ve  # noqa: PLC0415
        return _ve(v)

class ProfileData(BaseModel):
    alias: str
    curp: Optional[str] = None
    correo: Optional[str] = None
    nombre: Optional[str] = None
    placa: Optional[str] = None


# ── App & Routers ─────────────────────────────────────────────

app = FastAPI(
    title="Agente de Trámites GOB.MX",
    description="API REST para automatizar trámites gubernamentales mexicanos",
    version="1.0.0",
    docs_url=None if PROD else "/docs",
    redoc_url=None if PROD else "/redoc",
    openapi_tags=[
        {"name": "system", "description": "Health check e información general"},
        {"name": "tramites", "description": "Consultas de trámites (CURP, NSS)"},
        {"name": "perfiles", "description": "Gestión de perfiles de usuario"},
    ],
)

# CORS — restrictivo en producción (C2 del análisis)
# En producción, CORS_ORIGINS debe configurarse explícitamente (ej: https://misdominios.com)
# En desarrollo, permitimos * para facilitar testing local.
_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
if PROD:
    if not _CORS_ORIGINS:
        raise RuntimeError(
            "CORS_ORIGINS debe configurarse explícitamente en producción. "
            "Usá una lista separada por comas: https://app.misitio.com,https://admin.misitio.com"
        )
    origins = [o.strip() for o in _CORS_ORIGINS.split(",") if o.strip() and o.strip() != "*"]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (si está configurada API_KEY)
if API_KEY:
    app.middleware("http")(_verify_api_key)

system_router = APIRouter(tags=["system"])
tramites_router = APIRouter(tags=["tramites"])
perfiles_router = APIRouter(tags=["perfiles"])

if SLOWAPI_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    # No-op fallback para que los decoradores no rompan
    def _noop(f):
        return f

    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            return _noop
    limiter = _NoopLimiter()



# ── Captcha solver singleton ───────────────────────────────
# Inicializado UNA sola vez (H6 del análisis). Evita overhead
# de ~300-500ms por request verificando balance 2captcha siempre.
_SOLVER_CACHE = None


def _get_solver():
    """Retorna captcha solver singleton (2captcha o free)."""
    global _SOLVER_CACHE
    if _SOLVER_CACHE is not None:
        return _SOLVER_CACHE
    api_key = os.getenv("CAPTCHA_API_KEY", "")
    if api_key and api_key != "tu_api_key_aqui":
        try:
            _SOLVER_CACHE = CaptchaSolver(api_key)
            return _SOLVER_CACHE
        except CaptchaError:
            pass
    try:
        from src.utils.free_captcha import FreeCaptchaSolver
        _SOLVER_CACHE = FreeCaptchaSolver()
    except Exception:
        _SOLVER_CACHE = None
    return _SOLVER_CACHE


@system_router.get("/", summary="Información de la API")
@limiter.limit(_rate_limit("LIGHT", "30/minute"))
def root(request: Request):
    """Endpoint raíz — muestra metadatos de la app y lista de endpoints disponibles."""
    return {
        "app": "Agente de Trámites GOB.MX",
        "version": "1.0.0",
        "endpoints": {
            "GET  /health": "Health check",
            "POST /curp": "Consultar CURP",
            "POST /nss": "Obtener NSS IMSS",
            "GET  /perfiles": "Listar perfiles",
            "POST /perfiles": "Guardar perfil",
        }
    }


@system_router.get("/health", summary="Health check")
@limiter.limit(_rate_limit("LIGHT", "30/minute"))
def health(request: Request):
    """Verifica que la API esté operativa."""
    return {"status": "ok"}


@tramites_router.post("/curp", summary="Consultar CURP")
@limiter.limit(_rate_limit("CURP", "5/minute"))
async def consultar_curp(request: Request, req: CurpRequest):
    """Consulta una CURP en RENAPO y devuelve los datos de la persona."""
    solver = _get_solver()
    modulo = CURPModule(captcha_solver=solver)
    try:
        resultado = await modulo.consultar(curp=req.curp.upper())
        return {"success": True, "data": resultado}
    except TramiteError as e:
        logger.warning("Error CURP: %s", e)
        raise _tramite_exception_to_http(e) from e
    except Exception:
        logger.error("Error inesperado en consulta CURP", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@tramites_router.post("/nss", summary="Obtener NSS del IMSS")
@limiter.limit(_rate_limit("NSS", "5/minute"))
async def consultar_nss(request: Request, req: NssRequest):
    """Obtiene el NSS de una persona a través del IMSS usando CURP y correo."""
    solver = _get_solver()
    modulo = NSSModule(captcha_solver=solver)
    try:
        resultado = await modulo.consultar(
            curp=req.curp.upper(), correo=req.correo
        )
        return {"success": True, "data": resultado}
    except TramiteError as e:
        logger.warning("Error NSS: %s", e)
        raise _tramite_exception_to_http(e) from e
    except Exception:
        logger.error("Error inesperado en consulta NSS", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor")


@perfiles_router.get("/perfiles", summary="Listar perfiles guardados")
@limiter.limit(_rate_limit("PERFILES", "10/minute"))
def listar_perfiles(request: Request):
    """Devuelve la lista de todos los alias de perfiles guardados localmente."""
    try:
        perfiles = list_profiles()
        return {"perfiles": perfiles}
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Error listando perfiles: {e}")


@perfiles_router.post("/perfiles", summary="Guardar un perfil")
@limiter.limit(_rate_limit("PERFILES", "10/minute"))
def guardar_perfil(request: Request, data: ProfileData):
    """Guarda un perfil con datos persona (CURP, correo, nombre) bajo un alias."""
    try:
        profile = {k: v for k, v in data.model_dump().items() if v and k != "alias"}
        save_profile(data.alias, profile)
        return {"success": True, "alias": data.alias}
    except StorageError as e:
        raise HTTPException(status_code=500, detail=f"Error guardando perfil: {e}")


# ── Registrar routers (después de definir todas las rutas) ───

app.include_router(system_router)
app.include_router(tramites_router)
app.include_router(perfiles_router)
