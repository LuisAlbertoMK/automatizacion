"""
modules/tenencia.py
Automatiza la consulta y pago de Tenencia Vehicular (Estado de M\u00e9xico)
Portal: https://sfpya.edomexico.gob.mx/

Flujo:
  1. Abrir portal de tenencia
  2. Ingresar placa y n\u00famero de serie
  3. Resolver CAPTCHA si existe
  4. Generar formato de pago
  5. Descargar PDF
  6. Abrir autom\u00e1ticamente

Tiempo estimado: 20-40 segundos
"""

import asyncio
import re
import time

from playwright.async_api import Page

from src.exceptions import TenenciaError
from src.tramites.base import OUTPUT_DIR, BaseModule

TENENCIA_URL = "https://sfpya.edomexico.gob.mx/"
PORTAL_URL = "https://sfpya.edomexico.gob.mx/"

class TenenciaModule(BaseModule):
    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="TENENCIA")
        if use_ocr and self.ocr is None:
            self.warn("OCR no disponible")

    async def consultar(self, placa: str, numero_serie: str = None) -> dict:
        """
        Consulta tenencia vehicular y genera formato de pago.

        Args:
            placa: Placa vehicular (ej: ABC1234)
            numero_serie: N\u00famero de serie/VIN (opcional)

        Returns:
            dict con: monto, linea_captura, pdf_path, vigencia
        """
        if not placa:
            raise TenenciaError("Se requiere placa vehicular")

        placa = placa.upper().strip()
        self.log(f"Consultando tenencia para placa {placa}")
        start = time.time()

        br = await self.launch_browser()
        page = br.page
        try:
            result = await self._run(page, placa, numero_serie)
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return result
        finally:
            await self.close_browser(br)

    async def _run(self, page: Page, placa: str, numero_serie: str) -> dict:
        """Flujo principal."""

        # 1. Abrir portal
        self.log("Abriendo portal...")
        await self.goto(page, TENENCIA_URL, fallback_url=PORTAL_URL)

        # Screenshot para debug
        try:
            await page.screenshot(path="debug_tenencia.png")
            self.debug("Screenshot guardado: debug_tenencia.png")
        except Exception:
            self.debug("No se pudo cerrar sesion previa")

        # 2. Navegar a secci\u00f3n de tenencia si es necesario
        await self._navegar_a_tenencia(page)

        # 3. Ingresar placa
        await self._ingresar_placa(page, placa)

        # 4. Ingresar n\u00famero de serie si se proporciona
        if numero_serie:
            await self._ingresar_serie(page, numero_serie)

        # 5. Resolver CAPTCHA si existe
        await self._resolver_captcha(page)

        # 6. Consultar
        await self._enviar_consulta(page)

        # 7. Extraer informaci\u00f3n
        info = await self._extraer_informacion(page)

        # 8. Descargar formato de pago
        pdf_selectors = [
            "a:has-text('Descargar')",
            "button:has-text('Descargar')",
            "a:has-text('PDF')",
            "a:has-text('Imprimir')",
            "button:has-text('Generar')",
            "a[href*='.pdf']",
        ]
        pdf_path = await self.download_pdf(
            page, pdf_selectors,
            OUTPUT_DIR / f"Tenencia_{placa}_2026.pdf",
            name="Formato de pago"
        )
        info["pdf_path"] = str(pdf_path) if pdf_path else None

        return info

    async def _navegar_a_tenencia(self, page: Page):
        """Navega a la secci\u00f3n de tenencia si no est\u00e1 ah\u00ed."""
        await self.click_first(page, [
            "a:has-text('Tenencia')",
            "a:has-text('Control Vehicular')",
            "button:has-text('Tenencia')",
        ])
        self.log("Navegado a secci\u00f3n de tenencia")

    async def _ingresar_placa(self, page: Page, placa: str):
        """Ingresa la placa vehicular."""
        self.log(f"Ingresando placa: {placa}")

        filled = await self.fill_field(page, [
            "input[name='placa']",
            "input[id='placa']",
            "input[placeholder*='placa']",
            "input[placeholder*='Placa']",
            "input[name='txtPlaca']",
            "input[id='txtPlaca']",
        ], placa)

        if not filled:
            raise TenenciaError("No se encontr\u00f3 el campo de placa en el portal")
        self.log("Placa ingresada")

    async def _ingresar_serie(self, page: Page, numero_serie: str):
        """Ingresa el n\u00famero de serie/VIN."""
        self.log("Ingresando n\u00famero de serie...")

        filled = await self.fill_field(page, [
            "input[name='serie']",
            "input[id='serie']",
            "input[name='vin']",
            "input[id='vin']",
            "input[placeholder*='serie']",
            "input[placeholder*='VIN']",
            "input[name='numeroSerie']",
        ], numero_serie)

        if filled:
            self.log("N\u00famero de serie ingresado")
        else:
            self.warn("Campo de serie no encontrado (puede ser opcional)")

    async def _resolver_captcha(self, page: Page):
        """Resuelve CAPTCHA si existe. Usa solver o variable de entorno; fallback a manual."""
        solved = await self.resolve_image_captcha(
            page,
            img_selectors=[
                "img[src*='captcha']",
                "img[id*='captcha']",
                "img[src*='Captcha']",
            ],
            input_selectors=[
                "input[name='captcha']",
                "input[id='captcha']",
                "input[placeholder*='captcha']",
            ],
            numeric=True,
            captcha_name="tenencia"
        )
        if solved:
            return

        # Fallback manual via input()
        if await page.locator("img[src*='captcha'], img[id*='captcha'], img[src*='Captcha']").count() == 0:
            return

        self.log("Resuelve el CAPTCHA manualmente")
        solution = input("  Ingresa el CAPTCHA: ").strip()
        if solution:
            await self.fill_field(page, [
                "input[name='captcha']",
                "input[id='captcha']",
                "input[placeholder*='captcha']",
            ], solution)

    async def _enviar_consulta(self, page: Page):
        """Env\u00eda la consulta."""
        self.log("Enviando consulta...")

        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Consultar')",
            "button:has-text('Buscar')",
            "a:has-text('Consultar')",
            "#btnConsultar",
            "#btnBuscar",
        ]

        for sel in submit_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    self.debug(f"Haciendo clic en: {sel}")
                    await loc.first.click()
                    await asyncio.sleep(3)
                    self.log("Consulta enviada")
                    return
            except Exception as e:
                self.debug(f"Error con selector {sel}: {e}")
                continue

        raise TenenciaError("No se encontr\u00f3 el bot\u00f3n de consulta")

    async def _extraer_informacion(self, page: Page) -> dict:
        """Extrae informaci\u00f3n de la tenencia."""
        await asyncio.sleep(2)
        content = await page.content()

        # Extraer monto
        monto_match = re.search(r'\$\s*([\d,]+\.?\d*)', content)
        monto = monto_match.group(1) if monto_match else "No disponible"

        # Extraer l\u00ednea de captura
        linea_match = re.search(r'(\d{18,20})', content)
        linea_captura = linea_match.group(1) if linea_match else None

        self.log(f"Monto: ${monto}")
        if linea_captura:
            self.debug(f"L\u00ednea de captura: {linea_captura}")

        return {
            "monto": monto,
            "linea_captura": linea_captura,
            "vigencia": "2026",
        }
