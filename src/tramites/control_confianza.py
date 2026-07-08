"""
modules/control_confianza.py
Automatiza el llenado del Control de Confianza (SESNSP).
Portal: https://certificado.sesnsp.gob.mx/

Nota: Este trámite requiere intervención manual significativa
(login institucional, historial laboral, referencias, bienes).

Migrado de: tramites-auto/tramites-bot/tramites/control_confianza.js
"""

import time

from src.exceptions import ControlConfianzaError
from src.tramites.base import OUTPUT_DIR, BaseModule

PORTAL_URL = "https://certificado.sesnsp.gob.mx/"


class ControlConfianzaModule(BaseModule):
    """
    Módulo para el Control de Confianza (SESNSP).
    Requiere intervención manual para secciones complejas.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="ControlConfianza")

    async def consultar(self, curp: str, rfc: str = "", nombre: str = "",
                        fecha_nacimiento: str = "", estado_nacimiento: str = "",
                        domicilio: str = "", telefono: str = "", email: str = "",
                        estado_civil: str = "soltero", escolaridad: str = "licenciatura",
                        ingreso_mensual: int = 0, egreso_mensual: int = 0) -> dict:
        """
        Inicia el proceso de Control de Confianza.

        Args:
            curp: CURP
            rfc: RFC (opcional)
            nombre: Nombre completo
            fecha_nacimiento: Fecha de nacimiento (DD/MM/YYYY)
            estado_nacimiento: Estado de nacimiento
            domicilio: Domicilio (opcional)
            telefono: Teléfono (opcional)
            email: Email (opcional)
            estado_civil: Estado civil
            escolaridad: Escolaridad
            ingreso_mensual: Ingreso mensual bruto
            egreso_mensual: Egreso mensual estimado

        Returns:
            dict con status del proceso
        """
        if not curp:
            raise ControlConfianzaError("Se requiere CURP")

        self.log("Iniciando Control de Confianza...")
        start = time.time()

        async with self.browser_context() as br:
            page = br.page
            try:
                result = await self._run(page, curp=curp, rfc=rfc, nombre=nombre,
                                         fecha_nacimiento=fecha_nacimiento,
                                         estado_nacimiento=estado_nacimiento,
                                         domicilio=domicilio, telefono=telefono, email=email,
                                         estado_civil=estado_civil, escolaridad=escolaridad,
                                         ingreso_mensual=ingreso_mensual,
                                         egreso_mensual=egreso_mensual)
                elapsed = time.time() - start
                self.log(f"Control de Confianza completado en {elapsed:.1f}s")
                return result
            except ControlConfianzaError:
                raise
            except Exception as e:
                elapsed = time.time() - start
                self.error(f"Error en {elapsed:.1f}s: {e}")
                raise ControlConfianzaError(f"Error en Control de Confianza: {e}") from e

    async def _run(self, page, curp: str, rfc: str = "", nombre: str = "",
                   fecha_nacimiento: str = "", estado_nacimiento: str = "",
                   domicilio: str = "", telefono: str = "", email: str = "",
                   estado_civil: str = "soltero", escolaridad: str = "licenciatura",
                   ingreso_mensual: int = 0, egreso_mensual: int = 0) -> dict:
        """Flujo principal del Control de Confianza."""

        # ── 1. Navegar al portal ──────────────────────────────
        self.log("Abriendo portal SESNSP...")
        await self.goto(page, PORTAL_URL)

        self.log("⚠ Iniciá sesión con tu usuario institucional o e.firma en el navegador")
        await self.interaction.prompt_enter("Presioná Enter DESPUÉS de haber iniciado sesión...")

        # ── 2. Llenar datos personales ─────────────────────────
        await self.fill_field(page, ["#nombre", "input[name='nombre']"], nombre)
        await self.fill_field(page, ["#curp", "input[name='curp']"], curp.upper())
        if rfc:
            await self.fill_field(page, ["#rfc", "input[name='rfc']"], rfc.upper())
        if fecha_nacimiento:
            await self.fill_field(page, [
                "#fechaNacimiento", "input[name='fechaNac']"
            ], fecha_nacimiento)
        if estado_nacimiento:
            await self.fill_field(page, [
                "#lugarNacimiento", "input[name='lugarNac']"
            ], estado_nacimiento)
        if domicilio:
            await self.fill_field(page, [
                "#domicilio", "input[name='domicilio']"
            ], domicilio)
        if telefono:
            await self.fill_field(page, [
                "#telefono", "input[name='telefono']"
            ], telefono)
        if email:
            await self.fill_field(page, [
                "#email", "input[name='email']"
            ], email)

        # ── 3. Selects (estado civil, escolaridad) ──────────────
        for sel, valor in [
            (["#estadoCivil", "select[name='estadoCivil']"], estado_civil),
            (["#escolaridad", "select[name='escolaridad']"], escolaridad),
        ]:
            for s in sel:
                try:
                    self.debug(f"Buscando opcion: {s} = {valor}")
                    if await page.locator(s).count() > 0:
                        await page.select_option(s, valor)
                        break
                except Exception:
                    self.debug("Estado no encontrado")
                    continue

        # ── 4. Ingresos/egresos ─────────────────────────────────
        if ingreso_mensual:
            await self.fill_field(page, [
                "input[name='ingresoMensual']", "#ingresoMensual"
            ], str(ingreso_mensual))
        if egreso_mensual:
            await self.fill_field(page, [
                "input[name='egresoMensual']", "#egresoMensual"
            ], str(egreso_mensual))

        self.log("⚠ Completá el historial laboral, referencias y bienes manualmente")
        await self.interaction.prompt_enter("Presioná Enter cuando hayas completado TODO...")

        # ── 5. Enviar ──────────────────────────────────────────
        await self.click_first(page, [
            "button:has-text('Enviar')",
            "button:has-text('Guardar')",
            "#btnEnviar",
            "button[type='submit']",
        ], wait_nav=True)

        # ── 6. Descargar comprobante ───────────────────────────
        pdf_path = await self.download_pdf(
            page, [
                "a:has-text('Descargar')",
                "button:has-text('Descargar')",
                "a[href$='.pdf']",
                "#btnDescargar",
            ],
            OUTPUT_DIR / f"ControlConfianza_{curp[:8]}.pdf",
            name="Control PDF"
        )

        return {
            "status": "completado",
            "curp": curp.upper(),
            "pdf_path": str(pdf_path) if pdf_path else None,
        }
