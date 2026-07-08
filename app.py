#!/usr/bin/env python3
"""
app.py — Web UI con Streamlit para el Agente de Trámites GOB.MX.

Uso:
    streamlit run app.py
    # o via docker:
    docker compose --profile api run --service-ports app
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "config.env")
from src.utils.secrets_manager import init_secrets  # noqa: E402
init_secrets()

from src.tramites.curp import CURPModule  # noqa: E402
from src.tramites.nss import NSSModule  # noqa: E402
from src.tramites.orchestrator import listar_tramites  # noqa: E402
from src.utils.captcha import CaptchaError, CaptchaSolver  # noqa: E402
from src.utils.storage import (  # noqa: E402
    delete_profile,
    list_profiles,
    load_profile,
    save_profile,
)

# ── Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Trámites GOB.MX",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
)

API_KEY = os.getenv("CAPTCHA_API_KEY", "")


def _get_solver():
    if API_KEY and API_KEY != "tu_api_key_aqui":
        try:
            return CaptchaSolver(API_KEY)
        except CaptchaError:
            pass
    try:
        from src.utils.free_captcha import FreeCaptchaSolver
        return FreeCaptchaSolver()
    except Exception:
        return None


# ── Sidebar ─────────────────────────────────────────────────
st.sidebar.title("🤖 Trámites GOB.MX")
st.sidebar.caption(f"v1.0 · {datetime.now().strftime('%b %Y')}")

menu = st.sidebar.radio(
    "Menú",
    ["📊 Dashboard", "📋 CURP", "🔢 NSS IMSS", "👤 Perfiles", "⚙️ Configuración"]
)

if API_KEY and API_KEY != "tu_api_key_aqui":
    st.sidebar.success("✅ 2captcha conectado")
else:
    st.sidebar.warning("⚠️ Sin 2captcha — captchas manuales")


# ── Dashboard ───────────────────────────────────────────────
if menu == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.markdown("---")

    tramites = listar_tramites()

    col1, col2, col3 = st.columns(3)
    activos = sum(1 for t in tramites.values() if "Producción" in t["estado"])
    escritos = sum(1 for t in tramites.values() if "Escrito" in t["estado"])
    planif = sum(1 for t in tramites.values() if "Planificado" in t["estado"])

    col1.metric("✅ Producción", activos)
    col2.metric("🔶 Escritos", escritos)
    col3.metric("📋 Planificados", planif)

    st.markdown("### Estado de trámites")
    for nombre, info in tramites.items():
        emoji = "✅" if "Producción" in info["estado"] else "🔶" if "Escrito" in info["estado"] else "📋"
        st.markdown(f"- {emoji} **{nombre.upper()}**: {info['estado']} ({info['tiempo']})")

    st.markdown("### Acceso rápido")
    col_a, col_b = st.columns(2)
    if col_a.button("🔍 Consultar CURP", use_container_width=True):
        st.switch_page("app.py")
        st.session_state["page"] = "curp"
    if col_b.button("🔍 Consultar NSS", use_container_width=True):
        st.session_state["page"] = "nss"


# ── CURP ────────────────────────────────────────────────────
elif menu == "📋 CURP":
    st.title("📋 Consulta CURP")
    st.markdown("Consultá y descargá tu CURP oficial de RENAPO.")

    curp = st.text_input("CURP (18 caracteres)", max_chars=18,
                         help="Ej: GALJ800101HDFXXXX00").strip().upper()

    if st.button("🔍 Consultar CURP", type="primary", use_container_width=True):
        if not curp or len(curp) != 18:
            st.error("La CURP debe tener exactamente 18 caracteres")
        else:
            with st.spinner("Consultando CURP... (~16s)"):
                try:
                    solver = _get_solver()
                    modulo = CURPModule(captcha_solver=solver)
                    resultado = asyncio.run(modulo.consultar(curp=curp))

                    st.success("✅ CURP encontrada")
                    for k, v in resultado.items():
                        if v:
                            st.text_input(k.upper(), str(v), disabled=True)

                    if resultado.get("pdf_path"):
                        with open(resultado["pdf_path"], "rb") as f:
                            st.download_button(
                                "📄 Descargar PDF",
                                f,
                                file_name=f"curp_{curp}.pdf",
                            )
                except Exception as e:
                    st.error(f"Error: {e}")


# ── NSS ─────────────────────────────────────────────────────
elif menu == "🔢 NSS IMSS":
    st.title("🔢 NSS IMSS")
    st.markdown("Obtené tu Número de Seguridad Social del IMSS.")

    curp_nss = st.text_input("CURP", max_chars=18, key="curp_nss").strip().upper()
    correo = st.text_input("Correo electrónico", key="correo_nss").strip()

    if st.button("🔍 Obtener NSS", type="primary", use_container_width=True):
        if not curp_nss or len(curp_nss) != 18:
            st.error("CURP inválida")
        elif not correo or "@" not in correo:
            st.error("Correo inválido")
        else:
            with st.spinner("Consultando NSS... (~30-60s)"):
                try:
                    solver = _get_solver()
                    modulo = NSSModule(captcha_solver=solver)
                    resultado = asyncio.run(
                        modulo.consultar(curp=curp_nss, correo=correo)
                    )

                    if resultado.get("nss") == "ENVIADO_AL_CORREO":
                        st.info("📧 Solicitud enviada. Revisá tu correo.")
                    elif resultado.get("nss"):
                        st.success(f"✅ NSS: {resultado['nss']}")
                        for k, v in resultado.items():
                            if v:
                                st.text_input(k.upper(), str(v), disabled=True)
                    else:
                        st.warning("No se pudo obtener el NSS")
                except Exception as e:
                    st.error(f"Error: {e}")


# ── Perfiles ────────────────────────────────────────────────
elif menu == "👤 Perfiles":
    st.title("👤 Gestión de Perfiles")
    st.markdown("Guardá y cargá datos de clientes frecuentes.")

    perfiles = list_profiles()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Guardar perfil")
        alias = st.text_input("Alias (ej: juan_garcia)")
        p_curp = st.text_input("CURP", max_chars=18).strip().upper()
        p_correo = st.text_input("Correo")
        p_nombre = st.text_input("Nombre completo")
        p_placa = st.text_input("Placa (opcional)")

        if st.button("💾 Guardar", use_container_width=True):
            if alias and p_curp:
                data = {k: v for k, v in {
                    "curp": p_curp, "correo": p_correo,
                    "nombre": p_nombre, "placa": p_placa,
                }.items() if v}
                save_profile(alias, data)
                st.success(f"Perfil '{alias}' guardado")
                st.rerun()
            else:
                st.error("Alias y CURP son requeridos")

    with col2:
        st.subheader("Perfiles guardados")
        if perfiles:
            for p in perfiles:
                with st.expander(p):
                    profile = load_profile(p)
                    if profile:
                        for k, v in profile.items():
                            if v and k != "tipo":
                                masked = v[:4] + "****" if k == "curp" else v
                                st.text(f"{k}: {masked}")
                    if st.button(f"🗑️ Eliminar {p}", key=f"del_{p}"):
                        delete_profile(p)
                        st.rerun()
        else:
            st.info("No hay perfiles guardados")


# ── Config ──────────────────────────────────────────────────
elif menu == "⚙️ Configuración":
    st.title("⚙️ Configuración")
    st.markdown("Estado actual del sistema y variables de entorno.")

    st.subheader("Variables de entorno")
    vars_to_show = {
        "CAPTCHA_API_KEY": "🔑 2captcha",
        "STORAGE_KEY": "🔐 Encriptación",
        "HEADLESS": "🌐 Navegador",
        "REQUEST_DELAY": "⏱️ Rate limit",
        "RECAPTCHA_AUTO": "🤖 reCAPTCHA auto",
    }

    for var, label in vars_to_show.items():
        val = os.getenv(var, "")
        if var == "CAPTCHA_API_KEY":
            val = val[:8] + "****" if val and val != "tu_api_key_aqui" else "⚠️ No configurada"
        elif var == "STORAGE_KEY":
            val = "✅ Configurada" if val else "❌ No configurada"
        elif var == "HEADLESS":
            val = "Oculto" if val == "true" else "Visible"
        elif var == "REQUEST_DELAY":
            val = f"{val}s" if val else "2s (default)"
        elif var == "RECAPTCHA_AUTO":
            val = "Automático" if val == "true" else "Manual"
        st.text_input(label, val, disabled=True)

    st.subheader("Estado del sistema")
    solver = _get_solver()
    if solver:
        st.success("✅ Captcha solver disponible")
    else:
        st.warning("⚠️ Sin solver de captcha")

    st.subheader("Comandos útiles")
    st.code("""
# CLI
python main.py --tramite curp --curp XXXX
python main.py --tramite nss --curp XXXX --correo a@b.com

# API
uvicorn src.api:app --reload

# Docker
docker compose run --rm tramites --help
docker compose --profile api up
    """)
