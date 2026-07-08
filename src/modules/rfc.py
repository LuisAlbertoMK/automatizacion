"""
modules/rfc.py
Automatiza la consulta/obtención del RFC en SAT.
Portal: https://www.sat.gob.mx/tramites/operacion/28753/obten-tu-rfc-con-la-clave-unica-de-registro-de-poblacion-(curp)

Migrado de: tramites-auto/tramites-bot/tramites/rfc.js
"""

import time

from src.exceptions import RFCError
from src.modules.base import OUTPUT_DIR, BaseModule

PORTAL_URL = (
    "https://www.sat.gob.mx/tramites/operacion/28753/"
    "obten-tu-rfc-con-la-clave-unica-de-registro-de-poblacion-(curp)"
)


class RFCModule(BaseModule):
    """
    Módulo para consultar/obtener el RFC desde el SAT usando CURP.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="RFC")

    async def consultar(self, curp: str, nombre: str = "", apellido_paterno: str = "",
                        apellido_materno: str = "") -> dict:
        """
        Consulta el RFC en el SAT.

        Args:
            curp: CURP de 18 caracteres
            nombre: Nombre (opcional)
            apellido_paterno: Apellido paterno (opcional)
            apellido_materno: Apellido materno (opcional)

        Returns:
            dict con: rfc, curp, nombre_completo
        """
        if not curp:
            raise RFCError("Se requiere CURP para consultar RFC")

        self.log("Iniciando consulta RFC...")
        start = time.time()

        br = await self.launch_browser()
        page = br.page
        try:
            result = await self._run(page, curp=curp, nombre=nombre,
                                     apellido_paterno=apellido_paterno,
                                     apellido_materno=apellido_materno)
            elapsed = time.time() - start
            self.log(f"RFC completado en {elapsed:.1f}s")
            return result
        except RFCError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise RFCError(f"Error consultando RFC: {e}") from e
        finally:
            await self.close_browser(br)

    async def _run(self, page, curp: str, nombre: str = "",
                   apellido_paterno: str = "", apellido_materno: str = "") -> dict:
        """Flujo principal de consulta RFC."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal SAT...")
        await self.goto(page, PORTAL_URL)

        # ── 2. Click "Iniciar trámite" ────────────────────────
        await self.click_first(page, [
            "a:has-text('Iniciar')",
            "a:has-text('Iniciar trámite')",
            "#btnIniciar",
            "a[href*='iniciar']",
        ], wait_nav=True)

        # ── 3. Llenar CURP ─────────────────────────────────────
        await self.fill_field(page, [
            "input[name='curp']",
            "#curp",
            "#CURP",
        ], curp.upper().strip())

        # ── 4. Llenar datos personales (opcional) ──────────────
        if nombre:
            await self.fill_field(page, [
                "input[name='nombre']",
                "#nombre",
                "#primerNombre",
            ], nombre)
        if apellido_paterno:
            await self.fill_field(page, [
                "input[name='apellidoPaterno']",
                "#apellidoPaterno",
                "#paterno",
            ], apellido_paterno)
        if apellido_materno:
            await self.fill_field(page, [
                "input[name='apellidoMaterno']",
                "#apellidoMaterno",
                "#materno",
            ], apellido_materno)

        # ── 5. Enviar formulario ───────────────────────────────
        await self.click_first(page, [
            "button[type='submit']",
            "#btnBuscar",
            "#btnContinuar",
            "button:has-text('Continuar')",
        ], wait_nav=True)

        # ── 6. Captcha (si aplica) ─────────────────────────────
        await self.resolve_image_captcha(
            page,
            img_selectors=[".captcha img", "#captcha img", "img[src*='captcha']"],
            input_selectors=["input[name='captcha']", "#captcha"],
            captcha_name="RFC"
        )

        # ── 7. Extraer resultado ───────────────────────────────
        await page.wait_for_timeout(2000)
        content = await page.content()

        import re
        rfc_match = re.search(r"\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b", content)
        rfc_val = rfc_match.group(1) if rfc_match else "NO_ENCONTRADO"

        if rfc_val == "NO_ENCONTRADO":
            self.warn("RFC no encontrado en el HTML — puede requerir intervención manual")

        # Descargar PDF si es posible
        pdf_path = await self.download_pdf(
            page, [
                "a:has-text('Descargar')",
                "button:has-text('Descargar')",
                "a[href$='.pdf']",
                "#btnDescargar",
            ],
            OUTPUT_DIR / f"RFC_{curp[:8]}.pdf",
            name="RFC PDF"
        )

        return {
            "rfc": rfc_val,
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
