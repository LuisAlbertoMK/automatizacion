"""
modules/cita_ine.py
Automatiza el agendamiento de cita en el INE.
Portal: https://www.ine.mx/credencial/citas/

Migrado de: tramites-auto/tramites-bot/tramites/cita_ine.js
"""

import time

from src.exceptions import CitaINEerror
from src.tramites.base import OUTPUT_DIR, BaseModule

PORTAL_URL = "https://www.ine.mx/credencial/citas/"


class CitaINEModule(BaseModule):
    """
    Módulo para agendar cita en el INE.
    Requiere intervención manual para captcha y selección de módulo.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="CitaINE")

    async def consultar(self, curp: str, nombre: str = "") -> dict:
        """
        Agenda cita en el INE.

        Args:
            curp: CURP de 18 caracteres
            nombre: Nombre (opcional)

        Returns:
            dict con: status, curp, pdf_path
        """
        if not curp:
            raise CitaINEerror("Se requiere CURP para cita INE")

        self.log("Iniciando cita INE...")
        start = time.time()

        br = await self.launch_browser()
        page = br.page
        try:
            result = await self._run(page, curp=curp, nombre=nombre)
            elapsed = time.time() - start
            self.log(f"Cita INE completada en {elapsed:.1f}s")
            return result
        except CitaINEerror:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise CitaINEerror(f"Error en cita INE: {e}") from e
        finally:
            await self.close_browser(br)

    async def _run(self, page, curp: str, nombre: str = "") -> dict:
        """Flujo principal de cita INE."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal INE...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Click "Agendar" / "Nueva cita" ──────────────────
        await self.click_first(page, [
            "a:has-text('Agendar')",
            "a:has-text('Nueva cita')",
            "#btnNuevaCita",
            "a:has-text('Cita')",
        ], wait_nav=True)

        # ── 3. Llenar CURP ─────────────────────────────────────
        await self.fill_field(page, [
            "input[name='curp']",
            "#curp",
            "input[placeholder*='CURP']",
        ], curp.upper().strip())

        # ── 4. Llenar nombre (opcional) ────────────────────────
        if nombre:
            await self.fill_field(page, [
                "input[name='nombre']",
                "#nombre",
            ], nombre)

        # ── 5. Enviar ──────────────────────────────────────────
        await self.click_first(page, [
            "button[type='submit']",
            "#btnBuscar",
            "#btnContinuar",
            "button:has-text('Continuar')",
        ], wait_nav=True)

        # ── 6. Captcha + selección de módulo ───────────────────
        self.log("⚠ Resolvé el captcha y seleccioná tu módulo de atención en el navegador")
        site_key = await self.detect_site_key(page)
        if site_key:
            await self.wait_for_recaptcha(page, max_wait=180, module_name=self.name)

        # Esperar a que seleccione módulo
        input("  Presioná Enter DESPUÉS de seleccionar tu módulo de atención...")

        # ── 7. Seleccionar fecha disponible ────────────────────
        await page.wait_for_timeout(1000)
        try:
            primer_slot = await page.query_selector(
                ".fecha-disponible:not(.ocupada), td.disponible, .dia-disponible"
            )
            if primer_slot:
                await primer_slot.click()
                await page.wait_for_timeout(1000)
                self.log("Fecha disponible seleccionada [OK]")
        except Exception as e:
            self.debug(f"No se pudo seleccionar fecha: {e}")

        self.log("⚠ Confirmá la cita en el navegador")
        input("  Presioná Enter DESPUÉS de confirmar la cita...")

        # ── 8. Descargar comprobante ───────────────────────────
        pdf_path = await self.download_pdf(
            page, [
                "a:has-text('Descargar')",
                "button:has-text('Descargar')",
                "a:has-text('Comprobante')",
                "a[href$='.pdf']",
                "#btnDescargar",
            ],
            OUTPUT_DIR / f"CitaINE_{curp[:8]}.pdf",
            name="Cita INE PDF"
        )

        return {
            "status": "cita_agendada",
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
