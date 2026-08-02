"""
modules/antecedentes.py
Automatiza el trámite de Constancia de Antecedentes No Penales (Federal)
Portal: https://constancias.oadprs.gob.mx/  (VIVO verificado 2026-08-02)

Flujo REAL del portal (sin registro de cuenta):
  1. Capturar CURP (o Llave MX opcional)
  2. Validar datos + nombre de padre/madre/tutor
  3. Generar solicitud: institución + razón + correo (inmodificable)
  4. Pago $240.00 MXN (desde ene-2026; acreditación 72h hábiles)
  5. Descarga por liga al correo (disponible 30 días)

Tiempo estimado: 45-90 segundos (sin contar acreditación de pago)
"""

import asyncio
import re
import time

from playwright.async_api import Page

from src.exceptions import AntecedentesError
from src.tramites.base import TIMEOUT, BaseModule

PORTAL_URL = "https://constancias.oadprs.gob.mx/"

class AntecedentesModule(BaseModule):
    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="ANTECEDENTES")

    async def consultar(self, curp: str, correo: str,
                        nombre_tutor: str = "", institucion: str = "",
                        razon: str = "") -> dict:
        """
        Tramita constancia de antecedentes no penales (sin registro de cuenta).

        Args:
            curp: CURP de 18 caracteres
            correo: Correo electrónico válido (liga de descarga de la constancia)
            nombre_tutor: Nombre del padre/madre/tutor que registró el nacimiento
            institucion: Institución que solicita la constancia
            razon: Motivo del trámite

        Returns:
            dict con: status, folio, curp, correo, nota
        """
        if not curp or not correo:
            raise AntecedentesError("Se requieren CURP y correo")

        curp = curp.upper().strip()
        if not re.match(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$", curp):
            raise AntecedentesError("CURP inválida (debe tener 18 caracteres)")
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", correo):
            raise AntecedentesError("Correo electrónico inválido")

        self.log(f"Iniciando trámite para CURP {curp[:4]}****")
        start = time.time()

        async with self.browser_context() as br:
            page = br.page
            result = await self._run(page, curp, correo, nombre_tutor, institucion, razon)
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return result

    async def _run(self, page: Page, curp: str, correo: str,
                   nombre_tutor: str = "", institucion: str = "",
                   razon: str = "") -> dict:
        """Flujo principal alineado al portal real (sin registro)."""

        # 1. Abrir portal
        self.log("Abriendo portal...")
        await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        await asyncio.sleep(2)

        # 2. Capturar CURP (flujo sin Llave MX)
        self.log("Capturando CURP...")
        await self.fill_field(page, [
            "input[name='curp']", "input[id='curp']",
            "input[placeholder*='CURP']", "input[type='text']",
        ], curp)
        await self.click_first(page, [
            "button:has-text('Continuar')",
            "button:has-text('Consultar')",
            "button:has-text('Buscar')",
            "button[type='submit']",
        ], wait_nav=True)

        # 3. Validar datos + tutor
        if nombre_tutor:
            await self.fill_field(page, [
                "input[name='nombreRegistro']",
                "input[name='nombreTutor']",
                "input[placeholder*='padre']",
                "input[placeholder*='madre']",
                "input[placeholder*='tutor']",
            ], nombre_tutor)

        # 4. Llenar solicitud
        await self._llenar_solicitud(page, institucion, razon, correo)

        # 5. Resolver reCAPTCHA (semiautomático)
        await self._resolver_recaptcha(page)

        # 6. Enviar solicitud
        await self._enviar_solicitud(page)

        # 7. Registrar folio si aparece
        folio = None
        try:
            folio_match = await page.locator("text=/FOLIO[:\\s]*[A-Z0-9-]{6,}/i").first.text_content(timeout=3000)
            if folio_match:
                folio = folio_match.strip()
                self.log(f"Folio: {folio}")
        except Exception:
            pass

        return {
            "status": "solicitado",
            "folio": folio,
            "curp": curp,
            "correo": correo,
            "nota": "Pago $240 MXN requerido; constancia llega por correo en ~72h hábiles",
        }

    async def _llenar_solicitud(self, page: Page, institucion: str = "",
                                razon: str = "", correo: str = ""):
        """Llena el formulario de solicitud: institución, razón y correo."""
        self.log("Llenando solicitud...")

        await self.click_first(page, [
            "button:has-text('Nueva solicitud')",
            "a:has-text('Solicitar constancia')",
            "button:has-text('Tramitar')",
        ])

        if institucion:
            await self.fill_field(page, [
                "select[name*='institucion']", "select[id*='institucion']",
                "input[name*='institucion']", "input[id*='institucion']",
                "input[placeholder*='instituci']",
            ], institucion)

        if razon:
            await self.fill_field(page, [
                "textarea[name*='razon']", "textarea[id*='razon']",
                "input[name*='razon']", "input[id*='razon']",
                "input[placeholder*='razon']", "input[placeholder*='motivo']",
            ], razon)

        if correo:
            await self.fill_field(page, [
                "input[type='email']", "input[name*='correo']", "input[id*='correo']",
                "input[placeholder*='correo']", "input[placeholder*='email']",
            ], correo)

        self.log("Solicitud llenada")

    async def _resolver_recaptcha(self, page: Page):
        """Resuelve reCAPTCHA en modo semiautomático."""
        await asyncio.sleep(1)

        recaptcha_presente = await page.locator("iframe[src*='recaptcha']").count() > 0
        if not recaptcha_presente:
            self.log("Sin reCAPTCHA detectado")
            return

        self.log("reCAPTCHA detectado")

        # Intentar audio challenge si el solver lo soporta
        audio_method = getattr(self.solver, 'solve_recaptcha_v2_audio', None) if self.solver else None
        if audio_method:
            self.log("Intentando audio challenge (Whisper)...")
            site_key = await self.detect_site_key(page)
            if site_key:
                token = await audio_method(page, site_key, PORTAL_URL)
                if token and token != "MANUAL":
                    self.log("reCAPTCHA resuelto con audio")
                    return

        # Fallback: esperar resolución manual usando base
        await self.wait_for_recaptcha(page, max_wait=120, module_name="ANTECEDENTES")

    async def _enviar_solicitud(self, page: Page):
        """Envía la solicitud."""
        self.log("Enviando solicitud...")

        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Enviar')",
            "button:has-text('Solicitar')",
            "button:has-text('Generar')",
        ]

        for sel in submit_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await asyncio.sleep(3)
                    self.log("Solicitud enviada")
                    return
            except Exception:
                self.debug("Selector no disponible")
                continue
