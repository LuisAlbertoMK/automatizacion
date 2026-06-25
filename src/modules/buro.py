"""
modules/buro.py
Automatiza la consulta del Reporte Especial de Buró de Crédito (gratis 1/año).
Portal: https://www.burodecredito.com.mx/reporte-especial

Migrado de: tramites-auto/tramites-bot/tramites/buro.js
"""

import time

from exceptions import BuroError
from modules.base import OUTPUT_DIR, BaseModule

PORTAL_URL = "https://www.burodecredito.com.mx/reporte-especial"


class BuroModule(BaseModule):
    """
    Módulo para consultar el Reporte Especial de Buró de Crédito.
    Requiere intervención manual para preguntas de seguridad y captcha.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="Buro")

    async def consultar(self, rfc: str, curp: str, nombre: str = "",
                        apellido_paterno: str = "", apellido_materno: str = "",
                        fecha_nacimiento: str = "") -> dict:
        """
        Consulta Reporte Especial de Buró de Crédito.

        Args:
            rfc: RFC
            curp: CURP
            nombre: Nombre
            apellido_paterno: Apellido paterno
            apellido_materno: Apellido materno
            fecha_nacimiento: Fecha de nacimiento (DD/MM/YYYY)

        Returns:
            dict con: status, pdf_path
        """
        if not rfc:
            raise BuroError("Se requiere RFC para consultar Buró")

        self.log("Iniciando consulta Buró de Crédito...")
        start = time.time()

        p, browser, page = await self.launch_browser()
        try:
            result = await self._run(page, rfc=rfc, curp=curp, nombre=nombre,
                                     apellido_paterno=apellido_paterno,
                                     apellido_materno=apellido_materno,
                                     fecha_nacimiento=fecha_nacimiento)
            elapsed = time.time() - start
            self.log(f"Buró completado en {elapsed:.1f}s")
            return result
        except BuroError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise BuroError(f"Error consultando Buró: {e}") from e
        finally:
            await self.close_browser(p, browser)

    async def _run(self, page, rfc: str, curp: str, nombre: str = "",
                   apellido_paterno: str = "", apellido_materno: str = "",
                   fecha_nacimiento: str = "") -> dict:
        """Flujo principal de consulta Buró."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal Buró de Crédito...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Llenar formulario ───────────────────────────────
        await self.fill_field(page, [
            "#rfc", "input[name='rfc']"
        ], rfc.upper().strip())
        await self.fill_field(page, [
            "#curp", "input[name='curp']"
        ], curp.upper().strip())
        if nombre:
            await self.fill_field(page, [
                "#nombre", "input[name='nombre']"
            ], nombre)
        if apellido_paterno:
            await self.fill_field(page, [
                "#primerApellido", "input[name='primerApellido']"
            ], apellido_paterno)
        if apellido_materno:
            await self.fill_field(page, [
                "#segundoApellido", "input[name='segundoApellido']"
            ], apellido_materno)
        if fecha_nacimiento:
            await self.fill_field(page, [
                "#fechaNacimiento", "input[name='fechaNacimiento']"
            ], fecha_nacimiento)

        # ── 3. Intervención manual ─────────────────────────────
        self.log("⚠ Completá las preguntas de seguridad y captcha en el navegador")
        input("  Presioná Enter DESPUÉS de completar las preguntas...")

        # ── 4. Descargar reporte ───────────────────────────────
        pdf_path = await self.download_pdf(
            page, [
                "#btnDescargar",
                "button:has-text('Descargar')",
                "button:has-text('Obtener')",
                "button:has-text('Obtener reporte')",
            ],
            OUTPUT_DIR / f"Buro_{rfc[:8]}.pdf",
            name="Buró PDF"
        )

        # Fallback: guardar pantalla como PDF
        if not pdf_path:
            try:
                await page.pdf(path=str(OUTPUT_DIR / f"Buro_{rfc[:8]}.pdf"))
                pdf_path = OUTPUT_DIR / f"Buro_{rfc[:8]}.pdf"
                self.log(f"Pantalla guardada como PDF: {pdf_path}")
            except Exception as e:
                self.debug(f"Error guardando pantalla: {e}")

        return {
            "status": "descargado" if pdf_path else "pendiente",
            "rfc": rfc.upper(),
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
