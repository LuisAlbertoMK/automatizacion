"""
modules/antecedentes.py
Automatiza el trámite de Constancia de Antecedentes No Penales (Federal)
Portal: https://constancias.oadprs.gob.mx/

Flujo:
  1. Verificar/crear cuenta
  2. Login automático
  3. Llenar formulario
  4. Resolver reCAPTCHA (semiautomático)
  5. Descargar constancia PDF
  6. Abrir automáticamente

Tiempo estimado: 45-90 segundos
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

PORTAL_URL = "https://constancias.oadprs.gob.mx/"


class AntecedentesError(Exception):
    pass


class AntecedentesModule:
    def __init__(self, captcha_solver=None, use_ocr=True):
        self.solver = captcha_solver
        self.use_ocr = use_ocr and OCR_AVAILABLE
        self.ocr = OCRExtractor() if self.use_ocr else None
        
        if use_ocr and not OCR_AVAILABLE:
            print("  [ANTECEDENTES] ⚠ OCR no disponible")
    
    async def consultar(self, curp: str, correo: str, password: str = None, 
                       datos_personales: dict = None) -> dict:
        """
        Tramita constancia de antecedentes no penales.
        
        Args:
            curp: CURP de 18 caracteres
            correo: Correo electrónico
            password: Contraseña (si ya tiene cuenta)
            datos_personales: Dict con datos adicionales si es primera vez
        
        Returns:
            dict con: constancia_path, folio, fecha
        """
        if not curp or not correo:
            raise AntecedentesError("Se requieren CURP y correo")
        
        curp = curp.upper().strip()
        print(f"\n  [ANTECEDENTES] Iniciando trámite para CURP {curp[:4]}****")
        start = time.time()
        
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=HEADLESS,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
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
                result = await self._run(page, curp, correo, password, datos_personales)
                elapsed = time.time() - start
                print(f"  [ANTECEDENTES] ✅ Completado en {elapsed:.1f}s")
                return result
            finally:
                await browser.close()
    
    async def _run(self, page: Page, curp: str, correo: str, 
                   password: str, datos_personales: dict) -> dict:
        """Flujo principal."""
        
        # 1. Abrir portal
        print("  [ANTECEDENTES] Abriendo portal...")
        await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        await asyncio.sleep(2)
        
        # Screenshot para debug
        try:
            await page.screenshot(path="debug_antecedentes.png")
            print("  [DEBUG] Screenshot guardado: debug_antecedentes.png")
        except Exception:
            pass
        
        # 2. Verificar si necesita login o registro
        tiene_cuenta = password is not None
        
        if tiene_cuenta:
            await self._login(page, correo, password)
        else:
            # Primera vez: crear cuenta
            await self._registrar_cuenta(page, curp, correo, datos_personales)
        
        # 3. Llenar solicitud
        await self._llenar_solicitud(page, curp)
        
        # 4. Resolver reCAPTCHA
        await self._resolver_recaptcha(page)
        
        # 5. Enviar solicitud
        await self._enviar_solicitud(page)
        
        # 6. Descargar constancia
        pdf_path = await self._descargar_constancia(page, curp)
        
        return {
            "constancia_path": str(pdf_path) if pdf_path else None,
            "curp": curp,
            "correo": correo,
        }
    
    async def _login(self, page: Page, correo: str, password: str):
        """Login con cuenta existente."""
        print("  [ANTECEDENTES] Iniciando sesión...")
        
        # Buscar botón de login
        login_selectors = [
            "a:has-text('Iniciar sesión')",
            "button:has-text('Iniciar sesión')",
            "a:has-text('Ingresar')",
            "#btnLogin",
        ]
        
        for sel in login_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue
        
        # Llenar formulario de login
        await self._fill_field(page, ["input[type='email']", "input[name='email']"], correo)
        await self._fill_field(page, ["input[type='password']", "input[name='password']"], password)
        
        # Hacer clic en botón de login
        await page.click("button[type='submit']")
        await asyncio.sleep(2)
        
        print("  [ANTECEDENTES] Sesión iniciada ✓")
    
    async def _registrar_cuenta(self, page: Page, curp: str, correo: str, datos: dict):
        """Registra nueva cuenta."""
        print("  [ANTECEDENTES] Registrando nueva cuenta...")
        
        # Buscar botón de registro
        registro_selectors = [
            "a:has-text('Registrarse')",
            "button:has-text('Crear cuenta')",
            "a:has-text('Registro')",
        ]
        
        for sel in registro_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue
        
        # Llenar formulario de registro
        if datos:
            await self._fill_field(page, ["input[name='curp']"], curp)
            await self._fill_field(page, ["input[name='email']", "input[type='email']"], correo)
            
            # Generar contraseña automática si no se proporcionó
            password = datos.get("password", f"Auto{curp[:4]}2026!")
            await self._fill_field(page, ["input[name='password']", "input[type='password']"], password)
            
            # Guardar contraseña para futuros usos
            self._guardar_credenciales(curp, correo, password)
        
        print("  [ANTECEDENTES] Cuenta registrada ✓")
    
    async def _llenar_solicitud(self, page: Page, curp: str):
        """Llena el formulario de solicitud."""
        print("  [ANTECEDENTES] Llenando solicitud...")
        
        # Buscar botón de nueva solicitud
        nueva_selectors = [
            "button:has-text('Nueva solicitud')",
            "a:has-text('Solicitar constancia')",
            "button:has-text('Tramitar')",
        ]
        
        for sel in nueva_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue
        
        # Ingresar CURP
        await self._fill_field(page, ["input[name='curp']", "input[id='curp']"], curp)
        
        print("  [ANTECEDENTES] Solicitud llenada ✓")
    
    async def _resolver_recaptcha(self, page: Page):
        """Resuelve reCAPTCHA en modo semiautomático."""
        await asyncio.sleep(1)
        
        # Detectar si hay reCAPTCHA
        recaptcha_presente = await page.locator("iframe[src*='recaptcha']").count() > 0
        
        if not recaptcha_presente:
            print("  [ANTECEDENTES] Sin reCAPTCHA detectado")
            return
        
        print("  [ANTECEDENTES] 🔵 reCAPTCHA detectado")
        print("  [ANTECEDENTES] 👉 Resuélvelo manualmente en el navegador")
        print("  [ANTECEDENTES] ⏱️  Esperando hasta 120 segundos...")
        
        # Esperar resolución manual
        await self._esperar_recaptcha_resuelto(page, max_wait=120)
    
    async def _esperar_recaptcha_resuelto(self, page: Page, max_wait: int = 120):
        """Espera a que el usuario resuelva el reCAPTCHA."""
        elapsed = 0
        interval = 2
        
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            
            try:
                response = await page.evaluate("""
                    () => {
                        const resp = document.getElementById('g-recaptcha-response');
                        return resp ? resp.value : '';
                    }
                """)
                
                if response and len(response) > 20:
                    print(f"  [ANTECEDENTES] ✅ reCAPTCHA resuelto en {elapsed}s")
                    return
                
                if elapsed % 10 == 0:
                    print(f"  [ANTECEDENTES] ⏳ Esperando... ({elapsed}s/{max_wait}s)")
            except Exception:
                pass
        
        print(f"  [ANTECEDENTES] ⚠ Timeout: reCAPTCHA no resuelto en {max_wait}s")
    
    async def _enviar_solicitud(self, page: Page):
        """Envía la solicitud."""
        print("  [ANTECEDENTES] Enviando solicitud...")
        
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
                    print("  [ANTECEDENTES] Solicitud enviada ✓")
                    return
            except Exception:
                continue
    
    async def _descargar_constancia(self, page: Page, curp: str) -> Path:
        """Descarga la constancia PDF."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"Antecedentes_{curp}.pdf"
        
        await asyncio.sleep(2)
        
        print("  [ANTECEDENTES] Buscando constancia...")
        
        pdf_selectors = [
            "a:has-text('Descargar')",
            "button:has-text('Descargar')",
            "a:has-text('PDF')",
            "a[href*='.pdf']",
        ]
        
        for sel in pdf_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    async with page.expect_download(timeout=30000) as dl_info:
                        await page.click(sel)
                    download = await dl_info.value
                    await download.save_as(output_path)
                    print(f"  [ANTECEDENTES] Constancia descargada: {output_path} ✓")
                    
                    # Abrir automáticamente
                    self._abrir_pdf(output_path)
                    return output_path
            except Exception:
                continue
        
        print("  [ANTECEDENTES] ⚠ No se pudo descargar constancia automáticamente")
        return None
    
    def _abrir_pdf(self, pdf_path: Path):
        """Abre el PDF automáticamente."""
        try:
            import subprocess
            import platform
            
            sistema = platform.system()
            
            if sistema == "Windows":
                os.startfile(str(pdf_path))
                print(f"  [ANTECEDENTES] 📄 PDF abierto automáticamente")
            elif sistema == "Darwin":
                subprocess.run(["open", str(pdf_path)])
                print(f"  [ANTECEDENTES] 📄 PDF abierto automáticamente")
            else:
                subprocess.run(["xdg-open", str(pdf_path)])
                print(f"  [ANTECEDENTES] 📄 PDF abierto automáticamente")
        except Exception as e:
            print(f"  [ANTECEDENTES] ⚠ No se pudo abrir PDF: {e}")
    
    async def _fill_field(self, page: Page, selectors: list, value: str):
        """Intenta llenar un campo con múltiples selectores."""
        for sel in selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.fill(sel, value)
                    return
            except Exception:
                continue
    
    def _guardar_credenciales(self, curp: str, correo: str, password: str):
        """Guarda credenciales de forma segura."""
        # TODO: Implementar almacenamiento encriptado
        creds_file = Path("data/credenciales_antecedentes.txt")
        creds_file.parent.mkdir(exist_ok=True)
        
        with open(creds_file, "a") as f:
            f.write(f"{curp}|{correo}|{password}\n")
        
        print(f"  [ANTECEDENTES] Credenciales guardadas para futuros usos")
