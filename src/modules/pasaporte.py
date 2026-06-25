"""
modules/pasaporte.py
Automatiza la cita para Pasaporte SRE.
Portal: https://www.gob.mx/tramites/ficha/pasaporte-para-adultos/SRE230

Migrado de: tramites-auto/tramites-bot/tramites/pasaporte.js
"""

import time

from exceptions import PasaporteError
from modules.base import OUTPUT_DIR, BaseModule

PORTAL_URL = "https://www.gob.mx/tramites/ficha/pasaporte-para-adultos/SRE230"


class PasaporteModule(BaseModule):
    """
    Módulo para agendar cita de pasaporte en SRE.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="Pasaporte")

    async def consultar(self, curp: str, nombre: str = "", apellido_paterno: str = "",
                        apellido_materno: str = "", estado: str = "MEX",
                        telefono: str = "", email: str = "") -> dict:
        """
        Agenda cita de pasaporte.

        Args:
            curp: CURP de 18 caracteres
            nombre: Nombre (opcional)
            apellido_paterno: Apellido paterno (opcional)
            apellido_materno: Apellido materno (opcional)
            estado: Clave de estado/ delegación (default: MEX)
            telefono: Teléfono (opcional)
            email: Email (opcional)

        Returns:
            dict con: status, curp, cita_info
        """
        if not curp:
            raise PasaporteError("Se requiere CURP")

        self.log("Iniciando cita de pasaporte...")
        start = time.time()

        p, browser, page = await self.launch_browser()
        try:
            result = await self._run(page, curp=curp, nombre=nombre,
                                     apellido_paterno=apellido_paterno,
                                     apellido_materno=apellido_materno,
                                     estado=estado, telefono=telefono, email=email)
            elapsed = time.time() - start
            self.log(f"Cita pasaporte completada en {elapsed:.1f}s")
            return result
        except PasaporteError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise PasaporteError(f"Error en cita pasaporte: {e}") from e
        finally:
            await self.close_browser(p, browser)

    async def _run(self, page, curp: str, nombre: str = "", apellido_paterno: str = "",
                   apellido_materno: str = "", estado: str = "MEX",
                   telefono: str = "", email: str = "") -> dict:
        """Flujo principal de cita de pasaporte."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal SRE pasaporte...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Click "Iniciar trámite" / "cita" ───────────────
        await self.click_first(page, [
            "a:has-text('Iniciar trámite')",
            "a:has-text('cita')",
            "a[href*='citas']",
            "a:has-text('Agendar')",
        ], wait_nav=True)

        # ── 3. Seleccionar estado/delegación ───────────────────
        try:
            await page.wait_for_selector(
                "select[name='delegacion'], select[name='estado'], #delegacion",
                timeout=15000
            )
            selectors = ["select[name='delegacion']", "select[name='estado']", "#delegacion"]
            for sel in selectors:
                try:
                    if await page.locator(sel).count() > 0:
                        await page.select_option(sel, estado)
                        self.debug(f"Estado seleccionado: {estado}")
                        break
                except Exception:
                    continue
        except Exception as e:
            self.debug(f"Selector de estado no encontrado: {e}")

        # ── 4. Captcha ─────────────────────────────────────────
        await self.resolve_image_captcha(
            page,
            img_selectors=[".captcha img", "#captcha img", "img[src*='captcha']"],
            input_selectors=["input[name='captcha']", "#captcha"],
            captcha_name="Pasaporte"
        )

        # Esperar a que cargue el calendario
        await page.wait_for_timeout(3000)

        # ── 5. Seleccionar fecha disponible ────────────────────
        try:
            primer_slot = await page.query_selector(
                ".fecha-disponible:not(.ocupada), td.disponible, button.dia-disponible, .horario-libre"
            )
            if primer_slot:
                await primer_slot.click()
                await page.wait_for_timeout(1000)
                self.log("Fecha disponible seleccionada [OK]")
        except Exception as e:
            self.debug(f"No se pudo seleccionar fecha: {e}")

        # ── 6. Seleccionar horario disponible ──────────────────
        try:
            horario = await page.query_selector(
                ".horario-disponible:not(.ocupado), .hora-disponible, select[name='hora']"
            )
            if horario:
                tag = await horario.evaluate("el => el.tagName.toLowerCase()")
                if tag == "select":
                    options = await horario.query_selector_all("option:not([disabled])")
                    if len(options) > 1:
                        await horario.select_option(index=1)
                else:
                    await horario.click()
                self.log("Horario seleccionado [OK]")
        except Exception as e:
            self.debug(f"No se pudo seleccionar horario: {e}")

        # ── 7. Llenar datos personales ─────────────────────────
        await self.fill_field(page, [
            "input[name='nombre']",
            "#nombre",
        ], nombre)
        await self.fill_field(page, [
            "input[name='apPat']",
            "#apellidoPaterno",
            "input[name='apellidoPaterno']",
        ], apellido_paterno)
        await self.fill_field(page, [
            "input[name='apMat']",
            "#apellidoMaterno",
            "input[name='apellidoMaterno']",
        ], apellido_materno)
        await self.fill_field(page, [
            "input[name='curp']",
            "#curp",
        ], curp.upper().strip())
        await self.fill_field(page, [
            "input[name='telefono']",
            "#telefono",
        ], telefono)
        await self.fill_field(page, [
            "input[name='email']",
            "#email",
            "input[type='email']",
        ], email)

        # ── 8. Esperar confirmación manual si aplica reCAPTCHA ─
        self.log("Si hay reCAPTCHA, resolvelo en el navegador...")
        site_key = await self.detect_site_key(page)
        if site_key:
            await self.wait_for_recaptcha(page, max_wait=120, module_name=self.name)

        # ── 9. Descargar comprobante ───────────────────────────
        pdf_path = await self.download_pdf(
            page, [
                "a:has-text('Descargar')",
                "button:has-text('Descargar')",
                "a:has-text('Comprobante')",
                "a[href$='.pdf']",
                "#btnDescargar",
            ],
            OUTPUT_DIR / f"Pasaporte_{curp[:8]}.pdf",
            name="Cita PDF"
        )

        return {
            "status": "cita_agendada",
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
