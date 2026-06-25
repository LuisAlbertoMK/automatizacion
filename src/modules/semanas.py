"""
modules/semanas.py
Automatiza la consulta de Semanas Cotizadas en IMSS.
Portal: https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asegurado

Migrado de: tramites-auto/tramites-bot/tramites/semanas.js
"""

import time

from exceptions import SemanasError
from modules.base import OUTPUT_DIR, BaseModule

PORTAL_URL = ("https://serviciosdigitales.imss.gob.mx/"
              "gestionAsegurados-web-externo/asegurado")


class SemanasModule(BaseModule):
    """
    Módulo para consultar semanas cotizadas en el IMSS.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="Semanas")

    async def consultar(self, curp: str, nss: str = "") -> dict:
        """
        Consulta semanas cotizadas en el IMSS.

        Args:
            curp: CURP de 18 caracteres
            nss: NSS (opcional, si se tiene)

        Returns:
            dict con: semanas, nss, curp, pdf_path
        """
        if not curp:
            raise SemanasError("Se requiere CURP")

        self.log("Iniciando consulta de semanas cotizadas...")
        start = time.time()

        p, browser, page = await self.launch_browser()
        try:
            result = await self._run(page, curp=curp, nss=nss)
            elapsed = time.time() - start
            self.log(f"Semanas completadas en {elapsed:.1f}s")
            return result
        except SemanasError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise SemanasError(f"Error consultando semanas: {e}") from e
        finally:
            await self.close_browser(p, browser)

    async def _run(self, page, curp: str, nss: str = "") -> dict:
        """Flujo principal de consulta de semanas."""

        # ── 1. Navegar al portal IMSS ──────────────────────────
        self.log("Abriendo portal IMSS...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Llenar NSS o CURP ───────────────────────────────
        if nss:
            ok = await self.fill_field(page, [
                "input[name='nss']",
                "#nss",
            ], nss)
            if not ok:
                self.warn("Campo NSS no encontrado, intentando con CURP...")
        if not nss or not ok:
            await self.fill_field(page, [
                "input[name='curp']",
                "#curp",
            ], curp.upper().strip())

        # ── 3. Enviar formulario ───────────────────────────────
        await self.click_first(page, [
            "button[type='submit']",
            "#btnBuscar",
            "#btnConsultar",
            "button:has-text('Consultar')",
        ], wait_nav=True)

        # ── 4. Captcha ─────────────────────────────────────────
        await self.resolve_image_captcha(
            page,
            img_selectors=[".captcha img", "#captcha img", "img[src*='captcha']"],
            input_selectors=["input[name='captcha']", "#captcha"],
            captcha_name="Semanas"
        )

        # ── 5. Extraer resultados ──────────────────────────────
        await page.wait_for_timeout(2000)
        content = await page.content()

        import re
        semanas_match = re.search(r"(\d+)\s*(?:semanas?|semanas cotizadas)", content, re.IGNORECASE)
        semanas_val = semanas_match.group(1) if semanas_match else None

        # Descargar PDF
        pdf_path = await self.download_pdf(
            page, [
                "a:has-text('Descargar')",
                "button:has-text('Descargar')",
                "a[href$='.pdf']",
                "#btnDescargar",
                "a:has-text('Imprimir')",
            ],
            OUTPUT_DIR / f"Semanas_{curp[:8]}.pdf",
            name="Semanas PDF"
        )

        return {
            "semanas": semanas_val,
            "nss": nss or "CONSULTADO",
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
