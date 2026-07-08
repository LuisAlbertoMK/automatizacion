"""
modules/credito.py
Módulo unificado para consulta de Reportes de Crédito.
Reemplaza buro.py y circulo.py (~95% idénticos).

Portales:
  - Buró:     https://www.burodecredito.com.mx/reporte-especial
  - Círculo:  https://www.circulodecredito.com.mx/reporte-credito-especial
"""

import time
from typing import Literal

from src.exceptions import BuroError, CirculoError, ModuleError
from src.modules.base import OUTPUT_DIR, BaseModule

TipoCredito = Literal["buro", "circulo"]

_CONFIGS = {
    "buro": {
        "name": "Buro",
        "label": "Buró",
        "portal_url": "https://www.burodecredito.com.mx/reporte-especial",
        "error_cls": BuroError,
        "selectors": {
            "rfc":             ["#rfc", "input[name='rfc']"],
            "curp":            ["#curp", "input[name='curp']"],
            "nombre":          ["#nombre", "input[name='nombre']"],
            "primer_apellido": ["#primerApellido", "input[name='primerApellido']"],
            "segundo_apellido": ["#segundoApellido", "input[name='segundoApellido']"],
            "fecha_nacimiento": ["#fechaNacimiento", "input[name='fechaNacimiento']"],
            "descargar": [
                "#btnDescargar",
                "button:has-text('Descargar')",
                "button:has-text('Obtener')",
                "button:has-text('Obtener reporte')",
            ],
        },
        "pdf_pattern": "Buro_{rfc}.pdf",
        "msgs": {
            "start": "Iniciando consulta Buró de Crédito...",
            "portal": "Abriendo portal Buró de Crédito...",
            "done": "Buró completado en {elapsed:.1f}s",
            "pdf_saved": "Pantalla guardada como PDF: {path}",
        },
    },
    "circulo": {
        "name": "Circulo",
        "label": "Círculo",
        "portal_url": "https://www.circulodecredito.com.mx/reporte-credito-especial",
        "error_cls": CirculoError,
        "selectors": {
            "rfc":             ["input[name='rfc']", "#rfc"],
            "curp":            ["input[name='curp']", "#curp"],
            "nombre":          ["input[name='nombre']", "#nombre"],
            "primer_apellido": ["input[name='primerApellido']", "#primerApellido"],
            "segundo_apellido": ["input[name='segundoApellido']", "#segundoApellido"],
            "fecha_nacimiento": ["input[name='fechaNacimiento']", "#fechaNacimiento"],
            "descargar": [
                "#btnDescargar",
                "button:has-text('Descargar')",
                "button:has-text('Obtener reporte')",
                "button:has-text('Obtener')",
            ],
        },
        "pdf_pattern": "Circulo_{rfc}.pdf",
        "msgs": {
            "start": "Iniciando consulta Círculo de Crédito...",
            "portal": "Abriendo portal Círculo de Crédito...",
            "done": "Círculo completado en {elapsed:.1f}s",
            "pdf_saved": "Pantalla guardada como PDF: {path}",
        },
    },
}


class CreditoModule(BaseModule):
    """
    Módulo unificado para consultar Reportes de Crédito (Buró o Círculo).

    Args:
        tipo: "buro" o "circulo"
        captcha_solver: Solver de captcha opcional
        use_ocr: Usar OCR para extraer texto
    """

    def __init__(self, tipo: TipoCredito, captcha_solver=None, use_ocr=True):
        if tipo not in _CONFIGS:
            raise ModuleError(f"Tipo de crédito inválido: {tipo!r}")
        self._cfg = _CONFIGS[tipo]
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name=self._cfg["name"])

    async def consultar(self, rfc: str, curp: str, nombre: str = "",
                        apellido_paterno: str = "", apellido_materno: str = "",
                        fecha_nacimiento: str = "") -> dict:
        """
        Consulta Reporte Especial de Crédito.

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
        cfg = self._cfg
        ErrorCls = cfg["error_cls"]  # noqa: N806

        if not rfc:
            raise ErrorCls(f"Se requiere RFC para consultar {cfg['label']} de Crédito")

        self.log(cfg["msgs"]["start"])
        start = time.time()

        br = await self.launch_browser()
        page = br.page
        try:
            result = await self._run(page, rfc=rfc, curp=curp,
                                     nombre=nombre, apellido_paterno=apellido_paterno,
                                     apellido_materno=apellido_materno,
                                     fecha_nacimiento=fecha_nacimiento)
            elapsed = time.time() - start
            self.log(cfg["msgs"]["done"].format(elapsed=elapsed))
            return result
        except ErrorCls:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise ErrorCls(f"Error consultando {cfg['label']}: {e}") from e
        finally:
            await self.close_browser(br)

    async def _run(self, page, rfc: str, curp: str, nombre: str = "",
                   apellido_paterno: str = "", apellido_materno: str = "",
                   fecha_nacimiento: str = "") -> dict:
        """Flujo principal de consulta de crédito."""
        cfg = self._cfg
        sel = cfg["selectors"]

        # ── 1. Navegar al portal ──────────────────────────────
        self.log(cfg["msgs"]["portal"])
        await self.goto(page, cfg["portal_url"])

        # ── 2. Llenar formulario ───────────────────────────────
        await self.fill_field(page, sel["rfc"], rfc.upper().strip())
        await self.fill_field(page, sel["curp"], curp.upper().strip())
        if nombre:
            await self.fill_field(page, sel["nombre"], nombre)
        if apellido_paterno:
            await self.fill_field(page, sel["primer_apellido"], apellido_paterno)
        if apellido_materno:
            await self.fill_field(page, sel["segundo_apellido"], apellido_materno)
        if fecha_nacimiento:
            await self.fill_field(page, sel["fecha_nacimiento"], fecha_nacimiento)

        # ── 3. Intervención manual ─────────────────────────────
        self.log("⚠ Completá las preguntas de seguridad y captcha en el navegador")
        input("  Presioná Enter DESPUÉS de completar las preguntas...")

        # ── 4. Descargar reporte ───────────────────────────────
        pdf_name = cfg["pdf_pattern"].format(rfc=rfc[:8])
        pdf_path = await self.download_pdf(
            page, sel["descargar"],
            OUTPUT_DIR / pdf_name,
            name=f"{cfg['label']} PDF",
        )

        # Fallback: guardar pantalla como PDF
        if not pdf_path:
            try:
                pdf_path = OUTPUT_DIR / pdf_name
                await page.pdf(path=str(pdf_path))
                self.log(cfg["msgs"]["pdf_saved"].format(path=pdf_path))
            except Exception as e:
                self.debug(f"Error guardando pantalla: {e}")

        return {
            "status": "descargado" if pdf_path else "pendiente",
            "rfc": rfc.upper(),
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
