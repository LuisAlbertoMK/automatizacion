"""
modules/cedula_profesional.py
Automatiza la consulta de cédulas profesionales del registro de la SEP
Portal: https://www.cedulaprofesional.sep.gob.mx/  (VIVO verificado 2026-08-02)
Backend Solr público: https://search.sep.gob.mx/solr/cedulasCore/select

Flujo:
  1. (HTTP-first) Consultar el backend Solr público (JSON). Puede fallar
     desde datacenters por filtro geo/IP (conn-reset) → fallback navegador.
  2. (Fallback) Abrir portal, llenar formulario (por CURP o nombre) y parsear
     la página de resultados.
  3. Normalizar: número de cédula, título, institución, centro de trabajo,
     estatus y fechas.

Consulta gratuita, sin login, sin CAPTCHA.

Tiempo estimado: 15-30 segundos
"""

import asyncio
import re
import time

import requests
from playwright.async_api import Page

from src.exceptions import CedulaProfesionalError
from src.tramites.base import BaseModule

PORTAL_URL = "https://www.cedulaprofesional.sep.gob.mx/"
SOLR_URL = "https://search.sep.gob.mx/solr/cedulasCore/select"

# Patrón estándar de CURP (mismo que antecedentes/curp)
CURP_RE = r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class CedulaProfesionalModule(BaseModule):
    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr,
                         name="C\u00c9DULA PROFESIONAL")

    async def consultar(self, curp: str = None, nombre: str = "",
                        apellido_paterno: str = "", apellido_materno: str = "") -> dict:
        """
        Consulta cédulas profesionales en el registro de la SEP.

        Args:
            curp: CURP de 18 caracteres (modo primario — devuelve solo las
                  cédulas "vinculadas").
            nombre, apellido_paterno, apellido_materno: fallback por nombre
                  (cobertura total del padrón).

        Returns:
            dict con: status, tramite, fuente, curp, total, cedulas[]
        """
        if not curp and not (nombre or apellido_paterno or apellido_materno):
            raise CedulaProfesionalError(
                "Se requiere CURP o nombre/apellidos para la consulta"
            )

        if curp:
            curp = curp.upper().strip()
            if not re.match(CURP_RE, curp):
                raise CedulaProfesionalError(
                    "CURP inválida (debe tener 18 caracteres, formato AAAA######HAAAAA##)"
                )
        else:
            curp = ""

        self.log("Iniciando consulta de c\u00e9dula profesional...")
        start = time.time()

        # ── 1. HTTP-first: backend Solr (falla a veces desde datacenters) ──
        try:
            docs = await self._consulta_solr(
                curp=curp, nombre=nombre,
                apellido_paterno=apellido_paterno, apellido_materno=apellido_materno,
            )
            if docs is not None:
                resultado = self._normalizar_resultado(docs, curp=curp, fuente="solr")
                elapsed = time.time() - start
                self.log(f"Completado en {elapsed:.1f}s (Solr)")
                return resultado
        except Exception as e:
            self.warn(f"Solr HTTP no disponible ({e}) — usando navegador")

        # ── 2. Fallback: flujo de navegador ─────────────────────────────────
        async with self.browser_context() as br:
            page = br.page
            resultado = await self._run(
                page, curp=curp, nombre=nombre,
                apellido_paterno=apellido_paterno, apellido_materno=apellido_materno,
            )
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return resultado

    async def _consulta_solr(self, curp: str = "", nombre: str = "",
                             apellido_paterno: str = "", apellido_materno: str = ""):
        """Consulta el backend Solr de la SEP. Retorna docs o None si falló."""
        try:
            if curp:
                query = f'curp:"{curp}"'
            else:
                partes = [p for p in (apellido_paterno, apellido_materno, nombre) if p]
                query = " AND ".join(f'nombre:"{p}"' for p in partes) or "*:*"

            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None, lambda: requests.get(
                    SOLR_URL,
                    params={"q": query, "wt": "json", "rows": "50"},
                    timeout=15,
                    headers={"User-Agent": _UA},
                )
            )
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                return None
            docs = data.get("response", {}).get("docs")
            return docs if isinstance(docs, list) else None
        except Exception as e:
            self.debug(f"_consulta_solr falló: {e}")
            return None

    def _normalizar_resultado(self, docs: list, curp: str = "", fuente: str = "") -> dict:
        """Normaliza docs (Solr o navegador) a un resultado uniforme."""
        cedulas = []
        for doc in docs:
            cedulas.append({
                "numero": self._campo_solr(
                    doc, "numero_cedula", "cedula", "cedulaProfesional",
                    "numero", "noCedula", "cedula_profesional"),
                "titulo": self._campo_solr(doc, "titulo", "carrera", "profesion", "tituloO"),
                "institucion": self._campo_solr(
                    doc, "institucion", "escuela", "institucionEducativa",
                    "nombre_institucion"),
                "centro_trabajo": self._campo_solr(
                    doc, "centro_trabajo", "empleador", "lugar_trabajo", "trabajo"),
                "estatus": self._campo_solr(doc, "estatus", "status", "situacion"),
                "fecha_expedicion": self._campo_solr(
                    doc, "fecha_expedicion", "fecha", "fechaExpedicion", "anio"),
            })
        resultado = {
            "status": "ok",
            "tramite": "cedula_profesional",
            "fuente": fuente,
            "curp": curp or "",
            "total": len(cedulas),
            "cedulas": cedulas,
        }
        if not cedulas:
            resultado["nota"] = ("Sin resultados. Verificar datos o intentar "
                                 "por nombre/apellidos.")
        return resultado

    @staticmethod
    def _campo_solr(doc: dict, *keys) -> str:
        """Extrae el primer campo existente de un doc de Solr (lista o scalar)."""
        for k in keys:
            if k in doc:
                v = doc[k]
                if isinstance(v, list):
                    return " ".join(str(x) for x in v)
                return str(v)
        return ""

    async def _run(self, page: Page, curp: str = "", nombre: str = "",
                   apellido_paterno: str = "", apellido_materno: str = "") -> dict:
        """Flujo de navegador: formulario público + parseo de resultados."""
        self.log("Abriendo portal SEP...")
        await self.goto(page, PORTAL_URL)

        if curp:
            await self.fill_field(page, [
                "input[name*='curp']", "input[id*='curp']",
                "input[placeholder*='CURP']", "input[maxlength='18']",
            ], curp)
        else:
            await self.fill_field(page, [
                "input[name*='nombre']", "input[id*='nombre']",
                "input[placeholder*='Nombre']", "input[placeholder*='apellido']",
            ], f"{nombre} {apellido_paterno} {apellido_materno}".strip())

        await self.click_first(page, [
            "button:has-text('Consultar')",
            "button:has-text('Buscar')",
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Aceptar')",
        ])

        return await self._extraer_resultado(page, curp=curp)

    async def _extraer_resultado(self, page: Page, curp: str = "") -> dict:
        """Extrae cédulas de la página de resultados (regex sobre el HTML)."""
        await asyncio.sleep(1)
        content = await page.content()
        try:
            body_text = await page.inner_text("body")
        except Exception:
            body_text = ""

        # Números de cédula: bloques de 4-8 dígitos cerca de la etiqueta CÉDULA
        numeros = re.findall(r"(?:C(?:É|E)DULA[\s:]*)(\d{4,8})", content)
        if not numeros:
            numeros = re.findall(r"\b\d{5,8}\b", body_text)

        titulo = self._extraer_campo(body_text, r"T(?:Í|I)TULO")
        institucion = self._extraer_campo(body_text, r"INSTITUC(?:I|Ó|O)N")
        estatus = self._extraer_campo(body_text, r"ESTATUS")
        fecha = self._extraer_campo(body_text, r"FECHA")

        cedulas = []
        for num in dict.fromkeys(numeros):
            cedulas.append({
                "numero": num,
                "titulo": titulo,
                "institucion": institucion,
                "centro_trabajo": "",
                "estatus": estatus,
                "fecha_expedicion": fecha,
            })

        resultado = {
            "status": "ok",
            "tramite": "cedula_profesional",
            "fuente": "navegador",
            "curp": curp or "",
            "total": len(cedulas),
            "cedulas": cedulas,
        }
        if not cedulas:
            resultado["nota"] = ("Sin resultados. Verificar datos o intentar "
                                 "por nombre/apellidos.")
        return resultado

    @staticmethod
    def _extraer_campo(text: str, label: str) -> str:
        m = re.search(rf"{label}[\s:]+([^\n]+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else ""
