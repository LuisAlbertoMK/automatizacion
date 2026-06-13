"""
api.py — API REST para el Agente de Trámites GOB.MX.
Expone los trámites como endpoints HTTP con FastAPI.

Uso:
    uvicorn src.api:app --reload
    # o via docker: docker compose --profile api up
"""

import os
import sys
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query  # noqa: F401
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


# ── App ────────────────────────────────────────────────────

app = FastAPI(
    title="Agente de Trámites GOB.MX",
    description="API REST para automatizar trámites gubernamentales mexicanos",
    version="1.0.0",
)


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


@app.get("/")
def root():
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/curp")
async def consultar_curp(req: CurpRequest):
    """Consulta CURP vía RENAPO."""
    solver = _get_solver()
    modulo = CURPModule(captcha_solver=solver)
    try:
        resultado = await modulo.consultar(curp=req.curp.upper())
        return {"success": True, "data": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nss")
async def consultar_nss(req: NssRequest):
    """Obtiene NSS del IMSS."""
    solver = _get_solver()
    modulo = NSSModule(captcha_solver=solver)
    try:
        resultado = await modulo.consultar(
            curp=req.curp.upper(), correo=req.correo
        )
        return {"success": True, "data": resultado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/perfiles")
def listar_perfiles():
    perfiles = list_profiles()
    return {"perfiles": perfiles}


@app.post("/perfiles")
def guardar_perfil(data: ProfileData):
    profile = {k: v for k, v in data.model_dump().items() if v and k != "alias"}
    save_profile(data.alias, profile)
    return {"success": True, "alias": data.alias}
