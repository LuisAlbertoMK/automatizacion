"""
modules/acta_nacimiento.py
Automatiza la descarga del Acta de Nacimiento vía RENAPO.
Portal: https://www.gob.mx/actas

Migrado de: tramites-auto/tramites-bot/tramites/acta_nacimiento.js
"""

import time

from src.exceptions import ActaNacimientoError
from src.tramites.base import OUTPUT_DIR, BaseModule

PORTAL_URL = "https://www.gob.mx/actas"


class ActaNacimientoModule(BaseModule):
    """
    Módulo para descargar el Acta de Nacimiento desde RENAPO.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="ActaNacimiento")

    async def consultar(self, curp: str) -> dict:
        """
        Descarga el Acta de Nacimiento.

        Args:
            curp: CURP de 18 caracteres

        Returns:
            dict con: curp, pdf_path, status
        """
        if not curp:
            raise ActaNacimientoError("Se requiere CURP")

        self.log("Iniciando consulta de Acta de Nacimiento...")
        start = time.time()

        br = await self.launch_browser()
        page = br.page
        try:
            result = await self._run(page, curp=curp)
            elapsed = time.time() - start
            self.log(f"Acta completada en {elapsed:.1f}s")
            return result
        except ActaNacimientoError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise ActaNacimientoError(f"Error consultando acta: {e}") from e
        finally:
            await self.close_browser(br)

    async def _run(self, page, curp: str) -> dict:
        """Flujo principal de consulta de acta."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal gob.mx/actas...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Click "Obtener acta" ────────────────────────────
        await self.click_first(page, [
            "a:has-text('Obtener acta')",
            "a:has-text('Iniciar')",
            "a:has-text('Iniciar trámite')",
            "#btnIniciar",
        ], wait_nav=True)

        # ── 3. Llenar CURP ─────────────────────────────────────
        await self.fill_field(page, [
            "input[name='curp']",
            "#curp",
            "input[placeholder*='CURP']",
        ], curp.upper().strip())

        # ── 4. Enviar ──────────────────────────────────────────
        await self.click_first(page, [
            "button[type='submit']",
            "#btnBuscar",
            "#btnConsultar",
            "button:has-text('Consultar')",
        ], wait_nav=True)

        # ── 5. Captcha ─────────────────────────────────────────
        await self.resolve_image_captcha(
            page,
            img_selectors=[".captcha img", "#captcha img", "img[src*='captcha']"],
            input_selectors=["input[name='captcha']", "#captcha"],
            captcha_name="Acta"
        )

        # ── 6. Esperar resultados ──────────────────────────────
        await page.wait_for_timeout(2000)

        # ── 7. Descargar PDF ───────────────────────────────────
        pdf_path = await self.download_pdf(
            page, [
                "a:has-text('Descargar')",
                "button:has-text('Descargar')",
                "a[href$='.pdf']",
                "#btnDescargar",
                ".btn-descargar",
            ],
            OUTPUT_DIR / f"ActaNacimiento_{curp[:8]}.pdf",
            name="Acta PDF"
        )

        # Si no se descargó con download_pdf, intentar click en link PDF
        if not pdf_path:
            try:
                pdf_link = await page.query_selector("a[href$='.pdf']")
                if pdf_link:
                    href = await pdf_link.get_attribute("href")
                    if href:
                        from urllib.parse import urljoin

                        import requests
                        pdf_url = urljoin(page.url, href)
                        resp = requests.get(pdf_url, timeout=30)
                        if resp.status_code == 200:
                            path = OUTPUT_DIR / f"ActaNacimiento_{curp[:8]}.pdf"
                            path.write_bytes(resp.content)
                            pdf_path = path
                            self.log(f"Acta descargada: {pdf_path} [OK]")
            except Exception as e:
                self.debug(f"Error en descarga alternativa: {e}")

        return {
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
            "status": "descargado" if pdf_path else "pendiente",
        }
