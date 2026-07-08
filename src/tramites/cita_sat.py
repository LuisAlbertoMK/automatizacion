"""
modules/cita_sat.py
Automatiza el agendamiento de cita en el SAT.
Portal: https://citas.sat.gob.mx/

Migrado de: tramites-auto/tramites-bot/tramites/cita_sat.js
"""

import time

from src.exceptions import CitaSATError
from src.tramites.base import OUTPUT_DIR, BaseModule

PORTAL_URL = "https://citas.sat.gob.mx/"


class CitaSATModule(BaseModule):
    """
    Módulo para agendar cita en el SAT.
    Requiere intervención manual para captcha, selección de servicio y módulo.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="CitaSAT")

    async def consultar(self, rfc: str, curp: str = "", email: str = "") -> dict:
        """
        Agenda cita en el SAT.

        Args:
            rfc: RFC
            curp: CURP (opcional)
            email: Email (opcional)

        Returns:
            dict con: status, rfc, pdf_path
        """
        if not rfc:
            raise CitaSATError("Se requiere RFC para cita SAT")

        self.log("Iniciando cita SAT...")
        start = time.time()

        async with self.browser_context() as br:
            page = br.page
            try:
                result = await self._run(page, rfc=rfc, curp=curp, email=email)
                elapsed = time.time() - start
                self.log(f"Cita SAT completada en {elapsed:.1f}s")
                return result
            except CitaSATError:
                raise
            except Exception as e:
                elapsed = time.time() - start
                self.error(f"Error en {elapsed:.1f}s: {e}")
                raise CitaSATError(f"Error en cita SAT: {e}") from e

    async def _run(self, page, rfc: str, curp: str = "", email: str = "") -> dict:
        """Flujo principal de cita SAT."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal citas SAT...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Click "Nueva cita" / "Agendar" ──────────────────
        await self.click_first(page, [
            "a:has-text('Nueva cita')",
            "#btnNuevaCita",
            "a:has-text('Agendar')",
            "a:has-text('Cita')",
        ], wait_nav=True)

        # ── 3. Llenar RFC ──────────────────────────────────────
        await self.fill_field(page, [
            "input[name='rfc']",
            "#rfc",
            "input[placeholder*='RFC']",
        ], rfc.upper().strip())

        # ── 4. Llenar CURP (opcional) ──────────────────────────
        if curp:
            await self.fill_field(page, [
                "input[name='curp']",
                "#curp",
                "input[placeholder*='CURP']",
            ], curp.upper().strip())

        # ── 5. Llenar email (opcional) ─────────────────────────
        if email:
            await self.fill_field(page, [
                "input[name='email']",
                "#email",
                "input[type='email']",
            ], email)

        # ── 6. Enviar ──────────────────────────────────────────
        await self.click_first(page, [
            "button[type='submit']",
            "#btnContinuar",
            "#btnBuscar",
            "button:has-text('Continuar')",
        ], wait_nav=True)

        # ── 7. Captcha + selección de servicio ─────────────────
        self.log("⚠ Resolvé el captcha y seleccioná el servicio en el navegador")
        site_key = await self.detect_site_key(page)
        if site_key:
            await self.wait_for_recaptcha(page, max_wait=180, module_name=self.name)

        await self.interaction.prompt_enter("Presioná Enter DESPUÉS de seleccionar el servicio y módulo SAT...")

        # ── 8. Seleccionar fecha disponible ────────────────────
        await page.wait_for_timeout(1000)
        try:
            primer_slot = await page.query_selector(
                ".fecha-disponible:not(.ocupada), td.disponible, .horario-libre"
            )
            if primer_slot:
                await primer_slot.click()
                await page.wait_for_timeout(1000)
                self.log("Fecha disponible seleccionada [OK]")
        except Exception as e:
            self.debug(f"No se pudo seleccionar fecha: {e}")

        self.log("⚠ Confirmá la cita en el navegador")
        await self.interaction.prompt_enter("Presioná Enter DESPUÉS de confirmar la cita...")

        # ── 9. Descargar comprobante ───────────────────────────
        pdf_path = await self.download_pdf(
            page, [
                "a:has-text('Descargar')",
                "button:has-text('Descargar')",
                "a:has-text('Comprobante')",
                "a[href$='.pdf']",
                "#btnDescargar",
            ],
            OUTPUT_DIR / f"CitaSAT_{rfc[:8]}.pdf",
            name="Cita SAT PDF"
        )

        return {
            "status": "cita_agendada",
            "rfc": rfc.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
