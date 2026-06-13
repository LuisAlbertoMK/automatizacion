"""Tests para modules/orchestrator.py — orquestador de trámites."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from modules.orchestrator import TRAMITES_REGISTRADOS, listar_tramites  # noqa: E402

TRAMITES_ESPERADOS = [
    "curp", "nss", "antecedentes", "tenencia",
    "rfc", "semanas_imss", "pasaporte", "ine", "licencia",
]


class TestListarTramites:
    def test_listar_returns_all(self):
        tramites = listar_tramites()
        for t in TRAMITES_ESPERADOS:
            assert t in tramites, f"Falta trámite: {t}"
        assert len(tramites) == len(TRAMITES_ESPERADOS)

    def test_registrados_unchanged(self):
        """listar_tramites devuelve copia, no muta el original."""
        original_len = len(TRAMITES_REGISTRADOS)
        tramites = listar_tramites()
        tramites["fake_test"] = {"modulo": None, "estado": "test", "tiempo": "0s"}
        assert "fake_test" not in TRAMITES_REGISTRADOS
        assert len(TRAMITES_REGISTRADOS) == original_len

    def test_estructura_tramite(self):
        tramites = listar_tramites()
        for nombre, info in tramites.items():
            assert "modulo" in info
            assert "estado" in info
            assert "tiempo" in info

    def test_curp_estado_produccion(self):
        assert TRAMITES_REGISTRADOS["curp"]["estado"] == "✅ Producción"

    def test_nss_estado_produccion(self):
        assert TRAMITES_REGISTRADOS["nss"]["estado"] == "✅ Producción"

    def test_planificados_tienen_modulo_none(self):
        for nombre in ["rfc", "semanas_imss", "pasaporte", "ine", "licencia"]:
            assert TRAMITES_REGISTRADOS[nombre]["modulo"] is None
