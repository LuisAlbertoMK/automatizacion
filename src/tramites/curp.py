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

from src.exceptions import CURPError
from src.tramites.base import OUTPUT_DIR, BaseModule

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
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="CURP")
        if use_ocr and self.ocr is None:
            self.warn("OCR no disponible. Instala: pip install pytesseract pillow")

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

        self.log("Iniciando consulta...")
        start = time.time()

        br = await self.launch_browser()
        page = br.page
        try:
            result = await self._run(page, curp=curp, datos=datos)
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return result
        finally:
            await self.close_browser(br)

    async def _run(self, page: Page, curp: str = None, datos: dict = None) -> dict:
        """Flujo principal de consulta."""

        # ── 1. Abrir portal ────────────────────────────────────────
        self.log("Abriendo portal...")
        await self.goto(page, PORTAL_URL,
                        fallback_url=PORTAL_CONSULTA_URL)

        # Tomar screenshot para debug
        try:
            debug_path = str(OUTPUT_DIR / "debug_portal.png")
            await page.screenshot(path=debug_path)
            self.debug(f"Screenshot guardado: {debug_path}")
        except Exception as e:
            self.debug(f"Error guardando screenshot: {e}")

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
        self.log(f"Modo: por CURP ({curp[:4]}****)")

        # Esperar a que la página cargue completamente
        await asyncio.sleep(1)

        # Listar todos los inputs para debug
        all_inputs = await page.query_selector_all("input")
        self.debug(f"Total de inputs encontrados: {len(all_inputs)}")

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
            self.log("CURP ingresada")
            return

        # Si llegamos aquí, intentar un enfoque más agresivo
        self.debug("Intentando enfoque alternativo...")
        try:
            inputs = await self.find_visible_inputs(page, "curp")
            for inp_info in inputs:
                if "curp" in (inp_info["name"] + inp_info["id"] + inp_info["placeholder"]).lower():
                    await inp_info["element"].fill(curp.upper().strip())
                    self.log("CURP ingresada en campo detectado")
                    return
        except Exception as e:
            self.debug(f"Error en enfoque alternativo: {e}")

        raise CURPError("No se encontró el campo de CURP en el portal. Verifica que el portal esté accesible.")

    async def _consulta_por_datos(self, page: Page, datos: dict):
        """Llena el formulario de consulta por datos personales."""
        self.log("Modo: por datos personales")

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
            self.debug("No se pudo cerrar dialogo")

        # Estado
        estado_key = datos.get("estado", "").upper().replace("M\u00c9XICO", "MEXICO")
        estado_val = ESTADOS.get(estado_key, "MC")
        for sel in ["select[name='estado']", "#estadoNac"]:
            try:
                self.debug(f"Buscando selector de estado: {sel} = {estado_val}")
                if await page.locator(sel).count() > 0:
                    await page.select_option(sel, estado_val)
                    break
            except Exception:
                self.debug("Selector de estado no disponible")
                continue

        self.log("Datos personales ingresados")

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
            # gob.mx/curp nuevo portal
            "button.btn.btn-primary",
            "button[onclick*='buscar']",
        ]
        for sel in submit_selectors:
            try:
                if await page.locator(sel).count() > 0:
                    await page.click(sel)
                    await page.wait_for_timeout(2000)
                    self.log("Búsqueda enviada")
                    return
            except Exception:
                self.debug("Selector PDF no disponible")
                continue

        # Fallback: buscar cualquier botón con texto Buscar
        try:
            btn = page.get_by_role("button", name="Buscar")
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(2000)
                self.log("Búsqueda enviada (fallback role)")
                return
        except Exception:
            self.debug("No se pudo cerrar ventana")

        raise CURPError("No se encontr\u00f3 el bot\u00f3n de b\u00fasqueda")

    async def _extraer_resultado(self, page: Page) -> dict:
        """Extrae los datos de la p\u00e1gina de resultado usando HTML y OCR."""
        await asyncio.sleep(1)
        content = await page.content()
        body_text = await page.inner_text("body")

        # Extraer CURP del resultado
        curp_match = re.search(r"\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b", content)
        curp_val = curp_match.group(1) if curp_match else None

        # Extraer todos los campos del resultado (portal gob.mx/curp nuevo)
        def _campo(text: str, label: str) -> str:
            m = re.search(
                rf"{label}[:\s]+\s*([A-Za-z\u00c0-\u024f\u00f1\u00d1\s\d/]+?)(?:\n|$)",
                text,
            )
            return m.group(1).strip() if m else ""

        nombres = _campo(body_text, r"Nombre\(s\)")
        primer_ap = _campo(body_text, r"Primer apellido")
        segundo_ap = _campo(body_text, r"Segundo apellido")
        sexo = _campo(body_text, r"Sexo")
        fecha_nac = _campo(body_text, r"Fecha de nacimiento")
        nacionalidad = _campo(body_text, r"Nacionalidad")
        entidad_nac = _campo(body_text, r"Entidad de nacimiento")
        doc_probatorio = _campo(body_text, r"Documento probatorio")

        nombre = f"{nombres} {primer_ap} {segundo_ap}".strip()

        # Si no se encontraron datos, usar OCR como respaldo
        if (not curp_val or not nombre) and self.use_ocr and self.ocr:
            self.log("Usando OCR para extraer datos adicionales...")
            try:
                screenshot_path = "resultado_curp_temp.png"
                await page.screenshot(path=screenshot_path, full_page=True)

                ocr_data = self.ocr.extract_from_screenshot(screenshot_path)

                if not curp_val and ocr_data.get("curp"):
                    curp_val = ocr_data["curp"]
                    self.debug(f"CURP extraída: {curp_val}")

                if not nombre and ocr_data.get("raw_text"):
                    nombres = _campo(ocr_data["raw_text"], r"Nombre\(s\)")
                    primer_ap = _campo(ocr_data["raw_text"], r"Primer apellido")
                    segundo_ap = _campo(ocr_data["raw_text"], r"Segundo apellido")
                    nombre = f"{nombres} {primer_ap} {segundo_ap}".strip()
                    if nombre:
                        self.debug(f"Nombre extraído: {nombre}")

                try:
                    os.remove(screenshot_path)
                except Exception:
                    self.debug("Error procesando dato extra")
            except Exception as e:
                self.warn(f"Error al extraer datos: {e}")

        curp_val = curp_val or "DESCONOCIDA"
        result = {
            "curp": curp_val,
            "nombre": nombre or "",
            "nombres": nombres,
            "primer_apellido": primer_ap,
            "segundo_apellido": segundo_ap,
            "sexo": sexo,
            "fecha_nacimiento": fecha_nac,
            "nacionalidad": nacionalidad,
            "entidad_nacimiento": entidad_nac,
            "documento_probatorio": doc_probatorio,
        }
        self.log(f"Resultado: CURP={curp_val}, Nombre={nombre or '(pendiente PDF)'}")
        if sexo:
            self.debug(f"+ {nombres} {primer_ap} {segundo_ap} | {sexo} | {fecha_nac}")
        return result
