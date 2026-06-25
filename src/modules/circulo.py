"""
modules/circulo.py
Automatiza la consulta del Reporte de Crédito Especial de Círculo de Crédito (gratis 1/año).
Portal: https://www.circulodecredito.com.mx/reporte-credito-especial

Migrado de: tramites-auto/tramites-bot/tramites/circulo.js
"""

import time

from exceptions import CirculoError
from modules.base import OUTPUT_DIR, BaseModule

PORTAL_URL = "https://www.circulodecredito.com.mx/reporte-credito-especial"


class CirculoModule(BaseModule):
    """
    Módulo para consultar Reporte Especial de Círculo de Crédito.
    Requiere intervención manual para preguntas de seguridad y captcha.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="Circulo")

    async def consultar(self, rfc: str, curp: str, nombre: str = "",
                        apellido_paterno: str = "", apellido_materno: str = "",
                        fecha_nacimiento: str = "") -> dict:
        """
        Consulta Reporte Especial de Círculo de Crédito.

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
            raise CirculoError("Se requiere RFC para consultar Círculo de Crédito")

        self.log("Iniciando consulta Círculo de Crédito...")
        start = time.time()

        p, browser, page = await self.launch_browser()
        try:
            result = await self._run(page, rfc=rfc, curp=curp, nombre=nombre,
                                     apellido_paterno=apellido_paterno,
                                     apellido_materno=apellido_materno,
                                     fecha_nacimiento=fecha_nacimiento)
            elapsed = time.time() - start
            self.log(f"Círculo completado en {elapsed:.1f}s")
            return result
        except CirculoError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise CirculoError(f"Error consultando Círculo: {e}") from e
        finally:
            await self.close_browser(p, browser)

    async def _run(self, page, rfc: str, curp: str, nombre: str = "",
                   apellido_paterno: str = "", apellido_materno: str = "",
                   fecha_nacimiento: str = "") -> dict:
        """Flujo principal de consulta Círculo."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal Círculo de Crédito...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Llenar formulario ───────────────────────────────
        await self.fill_field(page, [
            "input[name='rfc']", "#rfc"
        ], rfc.upper().strip())
        await self.fill_field(page, [
            "input[name='curp']", "#curp"
        ], curp.upper().strip())
        if nombre:
            await self.fill_field(page, [
                "input[name='nombre']", "#nombre"
            ], nombre)
        if apellido_paterno:
            await self.fill_field(page, [
                "input[name='primerApellido']", "#primerApellido"
            ], apellido_paterno)
        if apellido_materno:
            await self.fill_field(page, [
                "input[name='segundoApellido']", "#segundoApellido"
            ], apellido_materno)
        if fecha_nacimiento:
            await self.fill_field(page, [
                "input[name='fechaNacimiento']", "#fechaNacimiento"
            ], fecha_nacimiento)

        # ── 3. Intervención manual ─────────────────────────────
        self.log("⚠ Completá las preguntas de seguridad y captcha en el navegador")
        input("  Presioná Enter DESPUÉS de completar...")

        # ── 4. Descargar reporte ───────────────────────────────
        pdf_path = await self.download_pdf(
            page, [
                "#btnDescargar",
                "button:has-text('Descargar')",
                "button:has-text('Obtener reporte')",
                "button:has-text('Obtener')",
            ],
            OUTPUT_DIR / f"Circulo_{rfc[:8]}.pdf",
            name="Círculo PDF"
        )

        # Fallback: guardar pantalla como PDF
        if not pdf_path:
            try:
                await page.pdf(path=str(OUTPUT_DIR / f"Circulo_{rfc[:8]}.pdf"))
                pdf_path = OUTPUT_DIR / f"Circulo_{rfc[:8]}.pdf"
                self.log(f"Pantalla guardada como PDF: {pdf_path}")
            except Exception as e:
                self.debug(f"Error guardando pantalla: {e}")

        return {
            "status": "descargado" if pdf_path else "pendiente",
            "rfc": rfc.upper(),
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
