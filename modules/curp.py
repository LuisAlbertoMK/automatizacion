"""
modules/curp.py
Automatiza la consulta y descarga de CURP en gob.mx/curp
Portal: https://consultas.curp.gob.mx/CurpSP/gobmx/default.jsp

Flujo:
  1. Abrir portal
  2. Seleccionar "Consulta por CURP" o "Consulta por datos"
  3. Ingresar CURP (o nombre + fecha + estado + sexo)
  4. Resolver CAPTCHA de imagen numérica (OCR o 2captcha)
  5. Descargar PDF

Tiempo estimado automatizado: 15–30 segundos
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
TIMEOUT    = int(os.getenv("TIMEOUT", "60")) * 1000
HEADLESS   = os.getenv("HEADLESS", "true").lower() == "true"

PORTAL_URL = "https://www.gob.mx/curp/"
PORTAL_CONSULTA_URL = "https://consultas.curp.gob.mx/CurpSP/"

# Mapa de claves de estado para el formulario
ESTADOS = {
    "AGUASCALIENTES":       "AS", "BAJA CALIFORNIA":     "BC",
    "BAJA CALIFORNIA SUR":  "BS", "CAMPECHE":             "CC",
    "CHIAPAS":              "CS", "CHIHUAHUA":            "CH",
    "CIUDAD DE MEXICO":     "DF", "COAHUILA":             "CL",
    "COLIMA":               "CM", "DURANGO":              "DG",
    "GUANAJUATO":           "GT", "GUERRERO":             "GR",
    "HIDALGO":              "HG", "JALISCO":              "JC",
    "ESTADO DE MEXICO":     "MC", "MICHOACAN":            "MN",
    "MORELOS":              "MS", "NAYARIT":              "NT",
    "NUEVO LEON":           "NL", "OAXACA":               "OC",
    "PUEBLA":               "PL", "QUERETARO":            "QT",
    "QUINTANA ROO":         "QR", "SAN LUIS POTOSI":      "SP",
    "SINALOA":              "SL", "SONORA":               "SR",
    "TABASCO":              "TC", "TAMAULIPAS":           "TS",
    "TLAXCALA":             "TL", "VERACRUZ":             "VZ",
    "YUCATAN":              "YN", "ZACATECAS":            "ZS",
    "NACIDO EN EXTRANJERO": "NE",
}


class CURPError(Exception):
    pass


class CURPModule:
    def __init__(self, captcha_solver=None, use_ocr=True):
        self.solver = captcha_solver
        self.use_ocr = use_ocr and OCR_AVAILABLE
        self.ocr = OCRExtractor() if self.use_ocr else None
        
        if use_ocr and not OCR_AVAILABLE:
            print("  [CURP] ⚠ OCR no disponible. Instala: pip install pytesseract pillow")

    async def consultar(self, curp: str = None, datos: dict = None) -> dict:
        """
        Consulta y descarga la CURP.

        Args:
            curp:  CURP de 18 caracteres (método directo, más rápido)
            datos: dict con nombre, primer_apellido, segundo_apellido,
                   fecha_nacimiento (DD/MM/YYYY), sexo (H/M), estado

        Returns:
            dict con: curp, nombre, pdf_path, estado_civil, nacimiento
        """
        if not curp and not datos:
            raise CURPError("Se requiere curp o datos personales")

        print("\n  [CURP] Iniciando consulta...")
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

            # Evitar detección de Playwright
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            try:
                result = await self._run(page, curp=curp, datos=datos)
                elapsed = time.time() - start
                print(f"  [CURP] ✅ Completado en {elapsed:.1f}s")
                return result
            finally:
                await browser.close()

    async def _run(self, page: Page, curp: str = None, datos: dict = None) -> dict:
        """Flujo principal de consulta."""

        # ── 1. Abrir portal ────────────────────────────────────────
        print("  [CURP] Abriendo portal...")
        try:
            await page.goto(PORTAL_CONSULTA_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        except Exception:
            # Fallback a URL alternativa
            await page.goto("https://consultas.curp.gob.mx/CurpSP/gobmx/inicio.jsp", wait_until="domcontentloaded", timeout=TIMEOUT)
        
        await asyncio.sleep(2)
        
        # Tomar screenshot para debug
        try:
            await page.screenshot(path="debug_portal.png")
            print("  [DEBUG] Screenshot guardado: debug_portal.png")
        except Exception:
            pass

        # ── 2. Elegir modalidad de consulta ───────────────────────
        if curp:
            await self._consulta_por_curp(page, curp)
        else:
            await self._consulta_por_datos(page, datos)

        # ── 3. Resolver CAPTCHA ────────────────────────────────────
        await self._resolver_captcha(page)

        # ── 4. Enviar formulario ───────────────────────────────────
        await self._enviar_busqueda(page)

        # ── 5. Extraer datos del resultado ─────────────────────────
        resultado = await self._extraer_resultado(page)

        # ── 6. Descargar PDF ───────────────────────────────────────
        pdf_path = await self._descargar_pdf(page, resultado.get("curp", "curp"))
        resultado["pdf_path"] = str(pdf_path) if pdf_path else None

        return resultado

    async def _consulta_por_curp(self, page: Page, curp: str):
        """Llena el formulario de consulta por CURP."""
        print(f"  [CURP] Modo: por CURP ({curp[:4]}****)")

        # Esperar a que la página cargue completamente
        await asyncio.sleep(1)
        
        # Listar todos los inputs para debug
        all_inputs = await page.query_selector_all("input")
        print(f"  [DEBUG] Total de inputs encontrados: {len(all_inputs)}")
        
        # Hacer clic en pestaña/botón de consulta por CURP (más selectores)
        tab_selectors = [
            "a[href*='porCurp']",
            "a[href*='curp']",
            "input[value='Por CURP']",
            "a:has-text('Por CURP')",
            "a:has-text('CURP')",
            "button:has-text('CURP')",
            "#consultaCurp",
            ".tab-curp",
            "li:has-text('CURP')",
            "[onclick*='curp']",
        ]
        
        tab_clicked = False
        for sel in tab_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    print(f"  [DEBUG] Haciendo clic en tab: {sel}")
                    await loc.first.click()
                    await asyncio.sleep(1)
                    tab_clicked = True
                    break
            except Exception as e:
                print(f"  [DEBUG] Error con selector {sel}: {e}")
                continue
        
        if tab_clicked:
            print("  [CURP] Tab de CURP activada ✓")

        # Ingresar CURP - selectores más amplios
        curp_inputs = [
            "input[name='curp']",
            "input[id='curp']",
            "input[id='txtCurp']",
            "input[name='txtCurp']",
            "input[placeholder*='CURP']",
            "input[placeholder*='curp']",
            "input[maxlength='18']",
            "input[type='text'][maxlength='18']",
            "#formConsultaCurp input[type='text']",
            "form input[type='text']:first-of-type",
        ]
        
        for sel in curp_inputs:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                if count > 0:
                    # Verificar si es visible
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Llenando campo CURP con selector: {sel}")
                        await loc.first.fill(curp.upper().strip())
                        await asyncio.sleep(0.3)
                        print(f"  [CURP] CURP ingresada ✓")
                        return
            except Exception as e:
                print(f"  [DEBUG] Error con input {sel}: {e}")
                continue

        # Si llegamos aquí, intentar un enfoque más agresivo
        print("  [DEBUG] Intentando enfoque alternativo...")
        try:
            # Buscar cualquier input de texto visible
            all_text_inputs = await page.query_selector_all("input[type='text'], input:not([type])")
            for inp in all_text_inputs:
                is_visible = await inp.is_visible()
                if is_visible:
                    name = await inp.get_attribute("name") or ""
                    id_attr = await inp.get_attribute("id") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    print(f"  [DEBUG] Input visible: name={name}, id={id_attr}, placeholder={placeholder}")
                    
                    # Si parece ser el campo de CURP
                    if "curp" in name.lower() or "curp" in id_attr.lower() or "curp" in placeholder.lower():
                        await inp.fill(curp.upper().strip())
                        print(f"  [CURP] CURP ingresada en campo detectado ✓")
                        return
        except Exception as e:
            print(f"  [DEBUG] Error en enfoque alternativo: {e}")

        raise CURPError("No se encontró el campo de CURP en el portal. Verifica que el portal esté accesible.")

    async def _consulta_por_datos(self, page: Page, datos: dict):
        """Llena el formulario de consulta por datos personales."""
        print("  [CURP] Modo: por datos personales")

        # Pestaña de datos
        for sel in ["a:has-text('Por Datos')", "#consultaDatos", ".tab-datos"]:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await asyncio.sleep(0.5)
                    break
            except Exception:
                continue

        # Nombre
        await self._fill_field(page, ["input[name='nombre']", "#nombre"], datos.get("nombre", ""))
        await self._fill_field(page, ["input[name='primerApellido']", "#apellido1"], datos.get("primer_apellido", ""))
        await self._fill_field(page, ["input[name='segundoApellido']", "#apellido2"], datos.get("segundo_apellido", ""))

        # Fecha de nacimiento
        fecha = datos.get("fecha_nacimiento", "")
        if fecha:
            await self._fill_field(page, ["input[name='fechaNac']", "#fechaNacimiento", "input[type='date']"], fecha)

        # Sexo
        sexo = datos.get("sexo", "H")
        for sel in [f"select[name='sexo'] option[value='{sexo}']", f"input[value='{sexo}']"]:
            try:
                if await page.locator(f"select[name='sexo']").count() > 0:
                    await page.select_option("select[name='sexo']", sexo)
                    break
            except Exception:
                continue

        # Estado
        estado_key = datos.get("estado", "").upper().replace("MÉXICO", "MEXICO")
        estado_val = ESTADOS.get(estado_key, "MC")
        for sel in ["select[name='estado']", "#estadoNac"]:
            try:
                if await page.locator(sel).count() > 0:
                    await page.select_option(sel, estado_val)
                    break
            except Exception:
                continue

        print("  [CURP] Datos personales ingresados ✓")

    async def _resolver_captcha(self, page: Page):
        """Detecta y resuelve el CAPTCHA del portal CURP."""
        await asyncio.sleep(1)

        # Detectar imagen de CAPTCHA
        captcha_selectors = [
            "img[src*='captcha']", "img[id*='captcha']",
            "img[src*='Captcha']", ".captcha img",
        ]

        captcha_img = None
        for sel in captcha_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    captcha_img = loc.first
                    break
            except Exception:
                continue

        if not captcha_img:
            print("  [CURP] Sin CAPTCHA detectado, continuando...")
            return

        print("  [CURP] CAPTCHA detectado, resolviendo...")

        # Tomar screenshot del captcha
        img_bytes = await captcha_img.screenshot()

        # Resolver CAPTCHA (2captcha, OCR gratuito o manual)
        solution = None
        if self.solver:
            try:
                solution = self.solver.solve_image(img_bytes, numeric=True)
                print(f"  [CURP] CAPTCHA resuelto: {solution}")
            except Exception as e:
                print(f"  [CURP] ⚠ Solver automático falló: {e}")
                print("  [CURP] → Modo manual como respaldo")

        if not solution:
            # Fallback: variable de entorno o manual
            solution = os.getenv("CAPTCHA_VALUE", "").strip()
            if solution:
                print(f"  [CURP] CAPTCHA desde CAPTCHA_VALUE: '{solution}'")
            else:
                print("  [CURP] ⚠ Sin CAPTCHA, continuando...")
                return

        # Ingresar solución
        captcha_inputs = [
            "input[name='captcha']", "input[id='captcha']",
            "input[placeholder*='captcha']", "input[placeholder*='Captcha']",
        ]
        for sel in captcha_inputs:
            try:
                if await page.locator(sel).count() > 0:
                    await page.fill(sel, solution)
                    print("  [CURP] CAPTCHA ingresado ✓")
                    return
            except Exception:
                continue

        raise CURPError("No se encontró el campo para ingresar el CAPTCHA")

    async def _enviar_busqueda(self, page: Page):
        """Hace clic en el botón de búsqueda."""
        submit_selectors = [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Buscar')", "button:has-text('Consultar')",
            "a:has-text('Buscar')", "#btnBuscar",
        ]
        for sel in submit_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
                    print("  [CURP] Búsqueda enviada ✓")
                    return
            except PwTimeout:
                pass
            except Exception:
                continue

        raise CURPError("No se encontró el botón de búsqueda")

    async def _extraer_resultado(self, page: Page) -> dict:
        """Extrae los datos de la página de resultado usando HTML y OCR."""
        await asyncio.sleep(1)
        content = await page.content()

        # Extraer CURP del resultado (HTML)
        curp_match = re.search(r"\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b", content)
        curp_val = curp_match.group(1) if curp_match else None

        # Nombre completo (heurística del HTML)
        nombre_match = re.search(
            r"(?:Nombre|NOMBRE)[:\s]+([A-ZÁÉÍÓÚÑ\s]+?)(?:\n|<|$)", content
        )
        nombre = nombre_match.group(1).strip() if nombre_match else ""
        
        # Si no se encontró CURP o nombre, usar OCR como respaldo
        if (not curp_val or not nombre) and self.use_ocr:
            print("  [CURP] Usando OCR para extraer datos adicionales...")
            try:
                # Tomar screenshot de la página de resultados
                screenshot_path = "resultado_curp_temp.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                
                # Extraer datos con OCR
                ocr_data = self.ocr.extract_from_screenshot(screenshot_path)
                
                if not curp_val and ocr_data["curp"]:
                    curp_val = ocr_data["curp"]
                    print(f"  [OCR] CURP extraída: {curp_val}")
                
                # Intentar extraer nombre del texto OCR
                if not nombre and ocr_data["raw_text"]:
                    nombre_ocr = re.search(
                        r"(?:Nombre|NOMBRE)[:\s]+([A-ZÁÉÍÓÚÑ\s]+?)(?:\n|$)",
                        ocr_data["raw_text"]
                    )
                    if nombre_ocr:
                        nombre = nombre_ocr.group(1).strip()
                        print(f"  [OCR] Nombre extraído: {nombre}")
                
                # Limpiar archivo temporal
                try:
                    os.remove(screenshot_path)
                except:
                    pass
            except Exception as e:
                print(f"  [OCR] Error al extraer datos: {e}")
        
        curp_val = curp_val or "DESCONOCIDA"
        result = {"curp": curp_val, "nombre": nombre}
        print(f"  [CURP] Resultado: CURP={curp_val}, Nombre={nombre or '(extraer del PDF)'}")
        return result

    async def _descargar_pdf(self, page: Page, curp: str) -> Path | None:
        """Descarga el PDF oficial de la CURP."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"CURP_{curp}.pdf"

        # Esperar a que aparezca el botón de descarga
        await asyncio.sleep(2)
        
        # Selectores más específicos para el PDF oficial
        pdf_selectors = [
            "a:has-text('Imprimir')",
            "button:has-text('Imprimir')",
            "a:has-text('PDF')",
            "a:has-text('Descargar')",
            "button:has-text('PDF')",
            "a[href*='.pdf']",
            "a[href*='imprimir']",
            "button[onclick*='imprimir']",
            "#btnImprimir",
            "#btnDescargar",
            ".btn-imprimir",
            "input[value*='Imprimir']",
        ]

        print("  [CURP] Buscando botón de descarga del PDF oficial...")
        
        for sel in pdf_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Intentando descargar con selector: {sel}")
                        try:
                            async with page.expect_download(timeout=30000) as dl_info:
                                await loc.first.click()
                            download = await dl_info.value
                            await download.save_as(output_path)
                            print(f"  [CURP] PDF oficial descargado: {output_path} ✓")
                            
                            # Abrir el PDF automáticamente
                            self._abrir_pdf(output_path)
                            return output_path
                        except Exception as e:
                            print(f"  [DEBUG] Error con selector {sel}: {e}")
                            continue
            except Exception:
                continue

        # Intentar buscar cualquier enlace o botón visible que pueda descargar el PDF
        print("  [DEBUG] Buscando enlaces de descarga alternativos...")
        try:
            all_links = await page.query_selector_all("a, button")
            for link in all_links:
                is_visible = await link.is_visible()
                if is_visible:
                    text = (await link.text_content() or "").lower()
                    href = await link.get_attribute("href") or ""
                    onclick = await link.get_attribute("onclick") or ""
                    
                    if any(keyword in text for keyword in ["imprimir", "pdf", "descargar"]) or \
                       "pdf" in href.lower() or "imprimir" in onclick.lower():
                        print(f"  [DEBUG] Encontrado: text='{text[:30]}', href={href[:50]}")
                        try:
                            async with page.expect_download(timeout=30000) as dl_info:
                                await link.click()
                            download = await dl_info.value
                            await download.save_as(output_path)
                            print(f"  [CURP] PDF oficial descargado: {output_path} ✓")
                            
                            # Abrir el PDF automáticamente
                            self._abrir_pdf(output_path)
                            return output_path
                        except Exception:
                            continue
        except Exception as e:
            print(f"  [DEBUG] Error buscando enlaces alternativos: {e}")

        # Si no se pudo descargar el PDF oficial, NO usar fallback de screenshot
        print(f"  [CURP] ⚠ No se encontró el botón de descarga del PDF oficial")
        print(f"  [CURP] ⚠ Verifica manualmente en el navegador y descarga el PDF")
        return None
    
    def _abrir_pdf(self, pdf_path: Path):
        """Abre el PDF automáticamente con el visor predeterminado del sistema."""
        try:
            import subprocess
            import platform
            
            sistema = platform.system()
            
            if sistema == "Windows":
                os.startfile(str(pdf_path))
                print(f"  [CURP] 📄 PDF abierto automáticamente")
            elif sistema == "Darwin":  # macOS
                subprocess.run(["open", str(pdf_path)])
                print(f"  [CURP] 📄 PDF abierto automáticamente")
            else:  # Linux
                subprocess.run(["xdg-open", str(pdf_path)])
                print(f"  [CURP] 📄 PDF abierto automáticamente")
        except Exception as e:
            print(f"  [CURP] ⚠ No se pudo abrir el PDF automáticamente: {e}")
            print(f"  [CURP] Abre manualmente: {pdf_path}")

    async def _fill_field(self, page: Page, selectors: list, value: str):
        """Intenta llenar un campo con múltiples selectores."""
        for sel in selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.fill(sel, value)
                    return
            except Exception:
                continue
