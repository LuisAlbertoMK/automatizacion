"""
modules/control_confianza.py
Automatiza el llenado del Control de Confianza (SESNSP).
Portal: https://certificado.sesnsp.gob.mx/  **MUERTO (DNS dead desde 2025)**

NOTA: El portal original ya no existe. El trámite de Certificado Único Policial
ahora se maneja a través de los Centros de Evaluación y Control de Confianza (CECC)
de cada estado. No hay portal federal unificado de reemplazo.

Migrado de: tramites-auto/tramites-bot/tramites/control_confianza.js
Updated: 2026-08-02 — Portal MUERTO confirmado. consultar() falla rápido con error
claro en lugar de navegar a un dominio inexistente. El flujo navegable completo
(_run) se eliminó por ser código inalcanzable (dead code) tras el fail-fast.

TODO: Revisar si CDMX u otros estados tienen portal online para CUP.
Alternativa: https://www.gob.mx/proteccionfederal/acciones-y-programas/evaluacion-y-control-de-confianza
"""

from src.exceptions import ControlConfianzaError
from src.tramites.base import BaseModule

PORTAL_URL = "https://certificado.sesnsp.gob.mx/"  # MUERTO — no usar
_PORTAL_MUERTO_MSG = (
    "El portal federal de Control de Confianza (certificado.sesnsp.gob.mx) fue "
    "eliminado (DNS dead desde 2025). Este trámite ahora se gestiona vía los "
    "Centros de Evaluación y Control de Confianza (CECC) de cada estado. "
    "No hay portal federal unificado de reemplazo."
)


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

        # Portal eliminado (DNS dead desde 2025) — fallar rápido con mensaje claro
        raise ControlConfianzaError(_PORTAL_MUERTO_MSG)
