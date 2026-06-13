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

Tiempo estimado automatizado: 15-30 segundos
"""

import asyncio
import os
import re
import time

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PwTimeout

from exceptions import CURPError
from modules.base import OUTPUT_DIR, TIMEOUT, BaseModule

try:
    from utils.ocr import OCRExtractor  # noqa: F401
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


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



class CURPModule(BaseModule):
    def __init__(self, captcha_solver=None, use_ocr=True):
        effective_ocr = use_ocr and OCR_AVAILABLE
        super().__init__(captcha_solver=captcha_solver, use_ocr=effective_ocr, name="CURP")
        self.use_ocr = effective_ocr
        if use_ocr and not OCR_AVAILABLE:
            print("  [CURP] \u26a0 OCR no disponible. Instala: pip install pytesseract pillow")

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

        p, browser, page = await self.launch_browser()
        try:
            result = await self._run(page, curp=curp, datos=datos)
            elapsed = time.time() - start
            print(f"  [CURP] \u2705 Completado en {elapsed:.1f}s")
            return result
        finally:
            await self.close_browser(p, browser)

    async def _run(self, page: Page, curp: str = None, datos: dict = None) -> dict:
        """Flujo principal de consulta."""

        # ── 1. Abrir portal ────────────────────────────────────────
        print("  [CURP] Abriendo portal...")
        await self.goto(page, PORTAL_CONSULTA_URL,
                        fallback_url="https://consultas.curp.gob.mx/CurpSP/gobmx/inicio.jsp")

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
        pdf_path = await self.download_pdf(
            page, pdf_selectors,
            OUTPUT_DIR / f"CURP_{resultado.get('curp', 'curp')}.pdf",
            name="PDF oficial"
        )
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

        # Hacer clic en pestaña/botón de consulta por CURP
        await self.click_first(page, [
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
        ])

        # Ingresar CURP - selectores más amplios
        filled = await self.fill_field(page, [
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
        ], curp.upper().strip())

        if filled:
            print("  [CURP] CURP ingresada \u2713")
            return

        # Si llegamos aquí, intentar un enfoque más agresivo
        print("  [DEBUG] Intentando enfoque alternativo...")
        try:
            inputs = await self.find_visible_inputs(page, "curp")
            for inp_info in inputs:
                if "curp" in (inp_info["name"] + inp_info["id"] + inp_info["placeholder"]).lower():
                    await inp_info["element"].fill(curp.upper().strip())
                    print("  [CURP] CURP ingresada en campo detectado \u2713")
                    return
        except Exception as e:
            print(f"  [DEBUG] Error en enfoque alternativo: {e}")

        raise CURPError("No se encontró el campo de CURP en el portal. Verifica que el portal esté accesible.")

    async def _consulta_por_datos(self, page: Page, datos: dict):
        """Llena el formulario de consulta por datos personales."""
        print("  [CURP] Modo: por datos personales")

        # Pestaña de datos
        await self.click_first(page, ["a:has-text('Por Datos')", "#consultaDatos", ".tab-datos"])

        # Nombre, apellidos
        await self.fill_field(page, ["input[name='nombre']", "#nombre"], datos.get("nombre", ""))
        await self.fill_field(page, ["input[name='primerApellido']", "#apellido1"], datos.get("primer_apellido", ""))
        await self.fill_field(page, ["input[name='segundoApellido']", "#apellido2"], datos.get("segundo_apellido", ""))

        # Fecha de nacimiento
        fecha = datos.get("fecha_nacimiento", "")
        if fecha:
            await self.fill_field(page, ["input[name='fechaNac']", "#fechaNacimiento", "input[type='date']"], fecha)

        # Sexo
        sexo = datos.get("sexo", "H")
        try:
            if await page.locator("select[name='sexo']").count() > 0:
                await page.select_option("select[name='sexo']", sexo)
        except Exception:
            pass

        # Estado
        estado_key = datos.get("estado", "").upper().replace("M\u00c9XICO", "MEXICO")
        estado_val = ESTADOS.get(estado_key, "MC")
        for sel in ["select[name='estado']", "#estadoNac"]:
            try:
                if await page.locator(sel).count() > 0:
                    await page.select_option(sel, estado_val)
                    break
            except Exception:
                continue

        print("  [CURP] Datos personales ingresados \u2713")

    async def _resolver_captcha(self, page: Page):
        """Detecta y resuelve el CAPTCHA del portal CURP."""
        await self.resolve_image_captcha(
            page,
            img_selectors=[
                "img[src*='captcha']", "img[id*='captcha']",
                "img[src*='Captcha']", ".captcha img",
            ],
            input_selectors=[
                "input[name='captcha']", "input[id='captcha']",
                "input[placeholder*='captcha']", "input[placeholder*='Captcha']",
            ],
            numeric=True,
            captcha_name="CURP"
        )

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
                    print("  [CURP] B\u00fasqueda enviada \u2713")
                    return
            except PwTimeout:
                pass
            except Exception:
                continue

        raise CURPError("No se encontr\u00f3 el bot\u00f3n de b\u00fasqueda")

    async def _extraer_resultado(self, page: Page) -> dict:
        """Extrae los datos de la p\u00e1gina de resultado usando HTML y OCR."""
        await asyncio.sleep(1)
        content = await page.content()

        # Extraer CURP del resultado (HTML)
        curp_match = re.search(r"\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b", content)
        curp_val = curp_match.group(1) if curp_match else None

        # Nombre completo (heur\u00edstica del HTML)
        nombre_match = re.search(
            r"(?:Nombre|NOMBRE)[:\s]+([A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1\s]+?)(?:\n|<|$)", content
        )
        nombre = nombre_match.group(1).strip() if nombre_match else ""

        # Si no se encontr\u00f3 CURP o nombre, usar OCR como respaldo
        if (not curp_val or not nombre) and self.use_ocr and self.ocr:
            print("  [CURP] Usando OCR para extraer datos adicionales...")
            try:
                screenshot_path = "resultado_curp_temp.png"
                await page.screenshot(path=screenshot_path, full_page=True)

                ocr_data = self.ocr.extract_from_screenshot(screenshot_path)

                if not curp_val and ocr_data["curp"]:
                    curp_val = ocr_data["curp"]
                    print(f"  [OCR] CURP extra\u00edda: {curp_val}")

                if not nombre and ocr_data["raw_text"]:
                    nombre_ocr = re.search(
                        r"(?:Nombre|NOMBRE)[:\s]+([A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1\s]+?)(?:\n|$)",
                        ocr_data["raw_text"]
                    )
                    if nombre_ocr:
                        nombre = nombre_ocr.group(1).strip()
                        print(f"  [OCR] Nombre extra\u00eddo: {nombre}")

                try:
                    os.remove(screenshot_path)
                except Exception:
                    pass
            except Exception as e:
                print(f"  [OCR] Error al extraer datos: {e}")

        curp_val = curp_val or "DESCONOCIDA"
        result = {"curp": curp_val, "nombre": nombre}
        print(f"  [CURP] Resultado: CURP={curp_val}, Nombre={nombre or '(extraer del PDF)'}")
        return result
