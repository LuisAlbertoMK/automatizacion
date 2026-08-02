"""Tests para src/tramites/control_confianza.py — Control de Confianza SESNSP.

El portal federal (certificado.sesnsp.gob.mx) está MUERTO (DNS dead desde 2025).
El módulo falla rápido con error claro en lugar de navegar a un dominio inexistente.
"""

import pytest

from src.exceptions import ControlConfianzaError
from src.tramites.control_confianza import _PORTAL_MUERTO_MSG, ControlConfianzaModule


class TestConsultar:
    async def test_sin_curp(self):
        """Sin CURP → error de validación (antes del chequeo de portal muerto)."""
        mod = ControlConfianzaModule()
        with pytest.raises(ControlConfianzaError, match="Se requiere CURP"):
            await mod.consultar(curp="")

    async def test_portal_muerto_hard_fail(self):
        """Portal muerto → falla rápido con mensaje claro, sin navegar."""
        mod = ControlConfianzaModule()
        with pytest.raises(ControlConfianzaError, match="portal federal de Control de Confianza"):
            await mod.consultar(curp="ABCD123456HDFRRN08")

    async def test_portal_muerto_mensaje_exacto(self):
        """El mensaje incluye la alternativa (CECC por estado)."""
        assert "CECC" in _PORTAL_MUERTO_MSG
        assert "DNS dead" in _PORTAL_MUERTO_MSG

    async def test_portal_muerto_no_navega(self):
        """No debe intentar abrir browser ni navegar (falla antes de browser_context)."""
        mod = ControlConfianzaModule()
        mod.browser_context = None  # si intentara navegar, explotaría con TypeError
        with pytest.raises(ControlConfianzaError, match="portal federal"):
            await mod.consultar(curp="ABCD123456HDFRRN08")
