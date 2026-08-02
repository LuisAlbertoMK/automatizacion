"""
modules/predial_cdmx.py
Automatiza la consulta de ADEUDO predial de CDMX (gratuita)
SPA: https://ovica.finanzas.cdmx.gob.mx/  (Oficina Virtual del Catastro)
Backend: https://sigapred.finanzas.cdmx.gob.mx/  (HTTP 200 desde datacenter)

Flujo:
  1. Abrir la SPA de OVICA y esperar el render de la app
  2. Ingresar cuenta predial (12 dígitos) o CLÚ
  3. Resolver CAPTCHA de imagen ("código de seguridad")
  4. Consultar adeudo
  5. Parsear: adeudo actual, monto, ejercicio(s), lista de adeudos

NO automatiza la constancia predial (pagada: $174 MXN + 24-48h).

Tiempo estimado: 20-40 segundos
"""

import asyncio
import re
import time

from playwright.async_api import Page

from src.exceptions import PredialError
from src.tramites.base import BaseModule

PORTAL_URL = "https://ovica.finanzas.cdmx.gob.mx/"
PORTAL_BACKEND_URL = "https://sigapred.finanzas.cdmx.gob.mx/"
PORTAL_PAGOS_URL = "https://data.finanzas.cdmx.gob.mx/consultas_pagos"

MONTO_RE = r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?"


class PredialCDMXModule(BaseModule):
    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr,
                         name="PREDIAL CDMX")

    async def consultar(self, cuenta: str = "", clu: str = "") -> dict:
        """
        Consulta el adeudo predial de un inmueble en CDMX.

        Args:
            cuenta: Cuenta predial de 12 dígitos (modo primario)
            clu: CLÚ (clave y valor catastral) — alternativo

        Returns:
            dict con: status, tramite, cuenta, clu, adeudo_actual, sin_adeudo,
                      monto, ejercicios, adeudos[]
        """
        cuenta = cuenta.strip() if cuenta else ""
        clu = clu.strip() if clu else ""

        if not cuenta and not clu:
            raise PredialError("Se requiere cuenta predial o CL\u00da")

        if cuenta and not re.match(r"^\d{12}$", cuenta):
            raise PredialError("Cuenta predial inv\u00e1lida (debe tener 12 d\u00edgitos)")

        self.log("Iniciando consulta de adeudo predial...")
        start = time.time()

        async with self.browser_context() as br:
            page = br.page
            resultado = await self._run(page, cuenta=cuenta, clu=clu)
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return resultado

    async def _run(self, page: Page, cuenta: str = "", clu: str = "") -> dict:
        """Flujo de consulta en la SPA de OVICA."""
        self.log("Abriendo OVICA...")
        await self.goto(page, PORTAL_URL)

        # SPA — esperar a que la app renderice antes de tocar selectores
        await page.wait_for_timeout(3000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            self.debug("networkidle no alcanzado — siguiendo igual")

        # Ingresar cuenta predial o CLÚ
        if cuenta:
            filled = await self.fill_field(page, [
                "input[name*='cuenta']", "input[id*='cuenta']",
                "input[placeholder*='cuenta']", "input[placeholder*='predial']",
                "input[maxlength='12']",
            ], cuenta)
        else:
            filled = await self.fill_field(page, [
                "input[name*='clu']", "input[id*='clu']",
                "input[placeholder*='clu']", "input[placeholder*='catastral']",
            ], clu)

        if not filled:
            raise PredialError("No se encontr\u00f3 el campo de cuenta predial en OVICA")

        # CAPTCHA de imagen ("código de seguridad")
        await self.resolve_image_captcha(
            page,
            img_selectors=[
                "img[src*='captcha']", "img[id*='captcha']",
                "img[src*='codigo']", "img[src*='Codigo']",
                "img[alt*='captcha']", ".captcha img",
            ],
            input_selectors=[
                "input[name*='captcha']", "input[id*='captcha']",
                "input[placeholder*='captcha']", "input[placeholder*='codigo']",
                "input[name*='codigo']",
            ],
            numeric=True,
            captcha_name="PREDIAL CDMX"
        )

        # Consultar adeudo
        await self.click_first(page, [
            "button:has-text('Consultar')", "button:has-text('Buscar')",
            "button:has-text('Adeudo')", "button[type='submit']",
            "input[type='submit']",
        ])

        # Esperar la respuesta de la SPA
        await page.wait_for_timeout(3000)

        return await self._parsear_adeudo(page, cuenta=cuenta, clu=clu)

    async def _parsear_adeudo(self, page: Page, cuenta: str = "", clu: str = "") -> dict:
        """Parsea el resultado de la consulta de adeudo."""
        await asyncio.sleep(1)
        try:
            content = await page.content()
        except Exception:
            content = ""
        try:
            body_text = await page.inner_text("body")
        except Exception:
            body_text = ""

        texto = re.sub(r"<[^>]+>", " ", content)
        texto = re.sub(r"\s+", " ", texto)

        sin_adeudo = bool(
            re.search(r"sin adeudo", texto, re.IGNORECASE)
            or re.search(r"sin adeudo", body_text, re.IGNORECASE)
        )

        montos = re.findall(MONTO_RE, texto) + re.findall(MONTO_RE, body_text)
        montos = list(dict.fromkeys(montos))

        ejercicios = list(dict.fromkeys(re.findall(r"\b(20\d{2})\b", body_text)))

        adeudos = []
        if montos and not sin_adeudo:
            for monto in montos:
                adeudos.append({
                    "ejercicio": ejercicios[0] if ejercicios else None,
                    "monto": monto,
                })

        if sin_adeudo:
            adeudo_actual = False
        elif montos:
            adeudo_actual = True
        else:
            adeudo_actual = None

        return {
            "status": "ok",
            "tramite": "predial_cdmx",
            "cuenta": cuenta,
            "clu": clu,
            "adeudo_actual": adeudo_actual,
            "sin_adeudo": sin_adeudo,
            "monto": montos[0] if montos else "$0.00",
            "ejercicios": ejercicios,
            "adeudos": adeudos,
        }
