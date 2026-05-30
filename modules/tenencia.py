"""
modules/tenencia.py
Automatiza la consulta y pago de Tenencia Vehicular (Estado de México)
Portal: https://sfpya.edomexico.gob.mx/

Flujo:
  1. Abrir portal de tenencia
  2. Ingresar placa y número de serie
  3. Resolver CAPTCHA si existe
  4. Generar formato de pago
  5. Descargar PDF
  6. Abrir automáticamente

Tiempo estimado: 20-40 segundos
"""

import os
import re
import time
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PwTimeout

try:
    from utils.ocr import OCRExtractor
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
TIMEOUT = int(os.getenv("TIMEOUT", "60")) * 1000
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

PORTAL_URL = "https://sfpya.edomexico.gob.mx/"
TENENCIA_URL = "https://sfpya.edomexico.gob.mx/controlv/faces/cv/consultas/ConsultaPagos/ConsultaPagos.xhtml"


class TenenciaError(Exception):
    pass


class TenenciaModule:
    def __init__(self, captcha_solver=None, use_ocr=True):
        self.solver = captcha_solver
        self.use_ocr = use_ocr and OCR_AVAILABLE
        self.ocr = OCRExtractor() if self.use_ocr else None
        
        if use_ocr and not OCR_AVAILABLE:
            print("  [TENENCIA] ⚠ OCR no disponible")
    
    async def consultar(self, placa: str, numero_serie: str = None) -> dict:
        """
        Consulta tenencia vehicular y genera formato de pago.
        
        Args:
            placa: Placa vehicular (ej: ABC1234)
            numero_serie: Número de serie/VIN (opcional)
        
        Returns:
            dict con: monto, linea_captura, pdf_path, vigencia
        """
        if not placa:
            raise TenenciaError("Se requiere placa vehicular")
        
        placa = placa.upper().strip()
        print(f"\n  [TENENCIA] Consultando tenencia para placa {placa}")
        start = time.time()
        
        async with async_playwright() as pw:
            browser = await pw.firefox.launch(
                headless=HEADLESS,
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                locale="es-MX",
            )
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
            
            try:
                result = await self._run(page, placa, numero_serie)
                elapsed = time.time() - start
                print(f"  [TENENCIA] ✅ Completado en {elapsed:.1f}s")
                return result
            finally:
                await browser.close()
    
    async def _run(self, page: Page, placa: str, numero_serie: str) -> dict:
        """Flujo principal."""
        
        # 1. Abrir portal
        print("  [TENENCIA] Abriendo portal...")
        try:
            await page.goto(TENENCIA_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        except Exception:
            # Fallback a URL principal
            await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        
        await asyncio.sleep(2)
        
        # Screenshot para debug
        try:
            await page.screenshot(path="debug_tenencia.png")
            print("  [DEBUG] Screenshot guardado: debug_tenencia.png")
        except Exception:
            pass
        
        # 2. Navegar a sección de tenencia si es necesario
        await self._navegar_a_tenencia(page)
        
        # 3. Ingresar placa
        await self._ingresar_placa(page, placa)
        
        # 4. Ingresar número de serie si se proporciona
        if numero_serie:
            await self._ingresar_serie(page, numero_serie)
        
        # 5. Resolver CAPTCHA si existe
        await self._resolver_captcha(page)
        
        # 6. Consultar
        await self._enviar_consulta(page)
        
        # 7. Extraer información
        info = await self._extraer_informacion(page)
        
        # 8. Descargar formato de pago
        pdf_path = await self._descargar_formato(page, placa)
        info["pdf_path"] = str(pdf_path) if pdf_path else None
        
        return info
    
    async def _navegar_a_tenencia(self, page: Page):
        """Navega a la sección de tenencia si no está ahí."""
        # Buscar enlaces/botones de tenencia
        tenencia_selectors = [
            "a:has-text('Tenencia')",
            "a:has-text('Control Vehicular')",
            "button:has-text('Tenencia')",
        ]
        
        for sel in tenencia_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await asyncio.sleep(1)
                    print("  [TENENCIA] Navegado a sección de tenencia ✓")
                    return
            except Exception:
                continue
    
    async def _ingresar_placa(self, page: Page, placa: str):
        """Ingresa la placa vehicular."""
        print(f"  [TENENCIA] Ingresando placa: {placa}")
        
        placa_selectors = [
            "input[name='placa']",
            "input[id='placa']",
            "input[placeholder*='placa']",
            "input[placeholder*='Placa']",
            "input[name='txtPlaca']",
            "input[id='txtPlaca']",
        ]
        
        for sel in placa_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Llenando placa con selector: {sel}")
                        await loc.first.fill(placa)
                        await asyncio.sleep(0.3)
                        print(f"  [TENENCIA] Placa ingresada ✓")
                        return
            except Exception as e:
                print(f"  [DEBUG] Error con selector {sel}: {e}")
                continue
        
        raise TenenciaError("No se encontró el campo de placa en el portal")
    
    async def _ingresar_serie(self, page: Page, numero_serie: str):
        """Ingresa el número de serie/VIN."""
        print(f"  [TENENCIA] Ingresando número de serie...")
        
        serie_selectors = [
            "input[name='serie']",
            "input[id='serie']",
            "input[name='vin']",
            "input[id='vin']",
            "input[placeholder*='serie']",
            "input[placeholder*='VIN']",
            "input[name='numeroSerie']",
        ]
        
        for sel in serie_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        await loc.first.fill(numero_serie)
                        await asyncio.sleep(0.3)
                        print(f"  [TENENCIA] Número de serie ingresado ✓")
                        return
            except Exception:
                continue
        
        print("  [TENENCIA] ⚠ Campo de serie no encontrado (puede ser opcional)")
    
    async def _resolver_captcha(self, page: Page):
        """Resuelve CAPTCHA si existe."""
        await asyncio.sleep(1)
        
        # Detectar CAPTCHA de imagen
        captcha_selectors = [
            "img[src*='captcha']",
            "img[id*='captcha']",
            "img[src*='Captcha']",
        ]
        
        captcha_selector = None
        for sel in captcha_selectors:
            if await page.locator(sel).count() > 0:
                captcha_selector = sel
                break
        
        if not captcha_selector:
            print("  [TENENCIA] Sin CAPTCHA detectado")
            return
        
        print("  [TENENCIA] 🔵 CAPTCHA detectado")
        
        solution = None
        if self.solver:
            try:
                # Tomar screenshot del captcha y resolver con OCR
                captcha_img = page.locator(captcha_selector).first
                img_bytes = await captcha_img.screenshot()
                solution = self.solver.solve_image(img_bytes, numeric=True)
                print(f"  [TENENCIA] CAPTCHA resuelto: {solution}")
            except Exception as e:
                print(f"  [TENENCIA] ⚠ Solver automático falló: {e}")

        if not solution:
            # Modo manual
            print("  [TENENCIA] 👉 Resuelve el CAPTCHA manualmente")
            solution = input("  Ingresa el CAPTCHA: ").strip()
            
            # Ingresar solución
            captcha_input_selectors = [
                "input[name='captcha']",
                "input[id='captcha']",
                "input[placeholder*='captcha']",
            ]
            
            for sel in captcha_input_selectors:
                try:
                    if await page.locator(sel).count() > 0:
                        await page.fill(sel, solution)
                        print("  [TENENCIA] CAPTCHA ingresado ✓")
                        return
                except Exception:
                    continue
    
    async def _enviar_consulta(self, page: Page):
        """Envía la consulta."""
        print("  [TENENCIA] Enviando consulta...")
        
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
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Haciendo clic en: {sel}")
                        await loc.first.click()
                        await asyncio.sleep(3)
                        print("  [TENENCIA] Consulta enviada ✓")
                        return
            except Exception as e:
                print(f"  [DEBUG] Error con selector {sel}: {e}")
                continue
        
        raise TenenciaError("No se encontró el botón de consulta")
    
    async def _extraer_informacion(self, page: Page) -> dict:
        """Extrae información de la tenencia."""
        await asyncio.sleep(2)
        content = await page.content()
        
        # Extraer monto
        monto_match = re.search(r'\$\s*([\d,]+\.?\d*)', content)
        monto = monto_match.group(1) if monto_match else "No disponible"
        
        # Extraer línea de captura
        linea_match = re.search(r'(\d{18,20})', content)
        linea_captura = linea_match.group(1) if linea_match else None
        
        print(f"  [TENENCIA] Monto: ${monto}")
        if linea_captura:
            print(f"  [TENENCIA] Línea de captura: {linea_captura}")
        
        return {
            "monto": monto,
            "linea_captura": linea_captura,
            "vigencia": "2026",
        }
    
    async def _descargar_formato(self, page: Page, placa: str) -> Path:
        """Descarga el formato de pago."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"Tenencia_{placa}_2026.pdf"
        
        print("  [TENENCIA] Buscando formato de pago...")
        
        pdf_selectors = [
            "a:has-text('Descargar')",
            "button:has-text('Descargar')",
            "a:has-text('PDF')",
            "a:has-text('Imprimir')",
            "button:has-text('Generar')",
            "a[href*='.pdf']",
        ]
        
        for sel in pdf_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    async with page.expect_download(timeout=30000) as dl_info:
                        await page.click(sel)
                    download = await dl_info.value
                    await download.save_as(output_path)
                    print(f"  [TENENCIA] Formato descargado: {output_path} ✓")
                    
                    # Abrir automáticamente
                    self._abrir_pdf(output_path)
                    return output_path
            except Exception:
                continue
        
        print("  [TENENCIA] ⚠ No se pudo descargar formato automáticamente")
        return None
    
    def _abrir_pdf(self, pdf_path: Path):
        """Abre el PDF automáticamente."""
        try:
            import subprocess
            import platform
            
            sistema = platform.system()
            
            if sistema == "Windows":
                os.startfile(str(pdf_path))
                print(f"  [TENENCIA] 📄 PDF abierto automáticamente")
            elif sistema == "Darwin":
                subprocess.run(["open", str(pdf_path)])
                print(f"  [TENENCIA] 📄 PDF abierto automáticamente")
            else:
                subprocess.run(["xdg-open", str(pdf_path)])
                print(f"  [TENENCIA] 📄 PDF abierto automáticamente")
        except Exception as e:
            print(f"  [TENENCIA] ⚠ No se pudo abrir PDF: {e}")
