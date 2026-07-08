"""
modules/antecedentes.py
Automatiza el tr\u00e1mite de Constancia de Antecedentes No Penales (Federal)
Portal: https://constancias.oadprs.gob.mx/

Flujo:
  1. Verificar/crear cuenta
  2. Login autom\u00e1tico
  3. Llenar formulario
  4. Resolver reCAPTCHA (semiautom\u00e1tico)
  5. Descargar constancia PDF
  6. Abrir autom\u00e1ticamente

Tiempo estimado: 45-90 segundos
"""

import asyncio
import time

from playwright.async_api import Page

from src.exceptions import AntecedentesError
from src.tramites.base import OUTPUT_DIR, TIMEOUT, BaseModule

PORTAL_URL = "https://constancias.oadprs.gob.mx/"

class AntecedentesModule(BaseModule):
    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="ANTECEDENTES")
        if use_ocr and self.ocr is None:
            self.warn("OCR no disponible")

    async def consultar(self, curp: str, correo: str, password: str = None,
                        datos_personales: dict = None) -> dict:
        """
        Tramita constancia de antecedentes no penales.

        Args:
            curp: CURP de 18 caracteres
            correo: Correo electr\u00f3nico
            password: Contrase\u00f1a (si ya tiene cuenta)
            datos_personales: Dict con datos adicionales si es primera vez

        Returns:
            dict con: constancia_path, folio, fecha
        """
        if not curp or not correo:
            raise AntecedentesError("Se requieren CURP y correo")

        curp = curp.upper().strip()
        self.log(f"Iniciando tr\u00e1mite para CURP {curp[:4]}****")
        start = time.time()

        async with self.browser_context() as br:
            page = br.page
            result = await self._run(page, curp, correo, password, datos_personales)
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return result

    async def _run(self, page: Page, curp: str, correo: str,
                   password: str, datos_personales: dict) -> dict:
        """Flujo principal."""

        # 1. Abrir portal
        self.log("Abriendo portal...")
        await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        await asyncio.sleep(2)

        # Screenshot para debug
        try:
            await page.screenshot(path="debug_antecedentes.png")
            self.debug("Screenshot guardado: debug_antecedentes.png")
        except Exception:
            self.debug("No se pudo cerrar sesion previa")

        # 2. Verificar si necesita login o registro
        tiene_cuenta = password is not None

        if tiene_cuenta:
            await self._login(page, correo, password)
        else:
            await self._registrar_cuenta(page, curp, correo, datos_personales)

        # 3. Llenar solicitud
        await self._llenar_solicitud(page, curp)

        # 4. Resolver reCAPTCHA
        await self._resolver_recaptcha(page)

        # 5. Enviar solicitud
        await self._enviar_solicitud(page)

        # 6. Descargar constancia
        pdf_selectors = [
            "a:has-text('Descargar')",
            "button:has-text('Descargar')",
            "a:has-text('PDF')",
            "a[href*='.pdf']",
        ]
        pdf_path = await self.download_pdf(
            page, pdf_selectors,
            OUTPUT_DIR / f"Antecedentes_{curp}.pdf",
            name="Constancia"
        )

        nueva_password = getattr(self, '_generated_password', None)
        result = {
            "constancia_path": str(pdf_path) if pdf_path else None,
            "curp": curp,
            "correo": correo,
        }
        if nueva_password:
            result["_nueva_password"] = nueva_password
            self.log("  [ANTECEDENTES] Contrasena generada (guardada en perfil)")
        return result

    async def _login(self, page: Page, correo: str, password: str):
        """Login con cuenta existente."""
        self.log("Iniciando sesi\u00f3n...")

        # Buscar bot\u00f3n de login
        await self.click_first(page, [
            "a:has-text('Iniciar sesi\u00f3n')",
            "button:has-text('Iniciar sesi\u00f3n')",
            "a:has-text('Ingresar')",
            "#btnLogin",
        ])

        # Llenar formulario de login
        await self.fill_field(page, ["input[type='email']", "input[name='email']"], correo)
        await self.fill_field(page, ["input[type='password']", "input[name='password']"], password)

        # Hacer clic en bot\u00f3n de login
        try:
            await page.click("button[type='submit']")
        except Exception:
            self.debug("Error en sub-paso del flujo")
        await asyncio.sleep(2)

        self.log("Sesi\u00f3n iniciada")

    async def _registrar_cuenta(self, page: Page, curp: str, correo: str, datos: dict):
        """Registra nueva cuenta."""
        self.log("Registrando nueva cuenta...")
        self._generated_password = None

        # Buscar bot\u00f3n de registro
        await self.click_first(page, [
            "a:has-text('Registrarse')",
            "button:has-text('Crear cuenta')",
            "a:has-text('Registro')",
        ])

        # Llenar formulario de registro
        if datos:
            await self.fill_field(page, ["input[name='curp']"], curp)
            await self.fill_field(page, ["input[name='email']", "input[type='email']"], correo)

            if "password" in datos:
                password = datos["password"]
            else:
                import secrets
                suffix = secrets.token_hex(4)  # 8 chars aleatorios
                password = f"Auto{curp[:4]}{suffix}!"
            self._generated_password = password
            await self.fill_field(page, ["input[name='password']", "input[type='password']"], password)

            self._guardar_credenciales(curp, correo, password)

        self.log("Cuenta registrada")

    async def _llenar_solicitud(self, page: Page, curp: str):
        """Llena el formulario de solicitud."""
        self.log("Llenando solicitud...")

        await self.click_first(page, [
            "button:has-text('Nueva solicitud')",
            "a:has-text('Solicitar constancia')",
            "button:has-text('Tramitar')",
        ])

        await self.fill_field(page, ["input[name='curp']", "input[id='curp']"], curp)

        self.log("Solicitud llenada")

    async def _resolver_recaptcha(self, page: Page):
        """Resuelve reCAPTCHA en modo semiautom\u00e1tico."""
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

        # Fallback: esperar resoluci\u00f3n manual usando base
        await self.wait_for_recaptcha(page, max_wait=120, module_name="ANTECEDENTES")

    async def _enviar_solicitud(self, page: Page):
        """Env\u00eda la solicitud."""
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

    def _guardar_credenciales(self, curp: str, correo: str, password: str):
        """Guarda credenciales de forma segura usando el almacenamiento encriptado."""
        try:
            from src.utils.storage import save_profile
            profile = {
                "curp": curp,
                "correo": correo,
                "password": password,
                "tipo": "antecedentes",
            }
            save_profile(f"antecedentes_{curp}", profile)
            self.log("Credenciales guardadas de forma segura")
        except Exception as e:
            self.warn(f"No se pudieron guardar credenciales: {e}")
            self.warn("Record\u00e1 tus credenciales para usos futuros.")
