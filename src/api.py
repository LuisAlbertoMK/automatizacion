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

import os
import sys
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, FastAPI, HTTPException, Query, Request  # noqa: F401
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# Asegurar path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / "config.env")


if not FASTAPI_AVAILABLE:
    import sys as _sys
    print("FastAPI no está instalado. Instalá con: pip install fastapi uvicorn")
    _sys.exit(1)


from modules.curp import CURPModule  # noqa: E402
from modules.nss import NSSModule  # noqa: E402
from utils.captcha import CaptchaError, CaptchaSolver  # noqa: E402
from utils.storage import list_profiles, save_profile  # noqa: E402

# ── Rate limiting (slowapi) ─────────────────────────────────

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    SLOWAPI_AVAILABLE = True
except ImportError:
    SLOWAPI_AVAILABLE = False


def _rate_limit(key: str, default: str) -> str:
    """Lee una variable de entorno o devuelve el default para rate limit."""
    return os.getenv(f"RATE_LIMIT_{key}", default)


# ── Models ─────────────────────────────────────────────────

class CurpRequest(BaseModel):
    curp: str
    perfil: Optional[str] = None

class NssRequest(BaseModel):
    curp: str
    correo: str
    perfil: Optional[str] = None

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
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "system", "description": "Health check e información general"},
        {"name": "tramites", "description": "Consultas de trámites (CURP, NSS)"},
        {"name": "perfiles", "description": "Gestión de perfiles de usuario"},
    ],
)

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



def _get_solver():
    """Inicializa captcha solver (2captcha o free)."""
    api_key = os.getenv("CAPTCHA_API_KEY", "")
    if api_key and api_key != "tu_api_key_aqui":
        try:
            return CaptchaSolver(api_key)
        except CaptchaError:
            pass
    try:
        from utils.free_captcha import FreeCaptchaSolver
        return FreeCaptchaSolver()
    except Exception:
        return None


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@perfiles_router.get("/perfiles", summary="Listar perfiles guardados")
@limiter.limit(_rate_limit("PERFILES", "10/minute"))
def listar_perfiles(request: Request):
    """Devuelve la lista de todos los alias de perfiles guardados localmente."""
    perfiles = list_profiles()
    return {"perfiles": perfiles}


@perfiles_router.post("/perfiles", summary="Guardar un perfil")
@limiter.limit(_rate_limit("PERFILES", "10/minute"))
def guardar_perfil(request: Request, data: ProfileData):
    """Guarda un perfil con datos persona (CURP, correo, nombre) bajo un alias."""
    profile = {k: v for k, v in data.model_dump().items() if v and k != "alias"}
    save_profile(data.alias, profile)
    return {"success": True, "alias": data.alias}


# ── Registrar routers (después de definir todas las rutas) ───

app.include_router(system_router)
app.include_router(tramites_router)
app.include_router(perfiles_router)
