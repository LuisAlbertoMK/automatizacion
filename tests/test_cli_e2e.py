"""E2E del entry point CLI real — ejecuta `python -m src.main` como proceso.

Cubre el contrato del binario publicado (`tramites = src.main:main`):
arranque, catálogo, validación de args y cierre del modo interactivo.
No mockea nada: es el flujo real de importación + argparse + main().
"""
import os
import subprocess
import sys
import time
from pathlib import Path

# Los módulos del proyecto tardan ~4-6s en importarse (playwright, PIL...)
_IMPORT_GRACE = 20


def _run_cli(args, stdin=None, timeout=30):
    t0 = time.monotonic()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"  # el CLI emite emojis; no depender del locale de la consola
    proc = subprocess.run(
        [sys.executable, "-m", "src.main", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        input=stdin,
        timeout=timeout,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    return proc, time.monotonic() - t0


class TestCliArranque:
    def test_help_sale_con_codigo_0(self):
        proc, elapsed = _run_cli(["--help"], timeout=_IMPORT_GRACE)
        assert proc.returncode == 0
        assert "--tramite" in proc.stdout
        assert "Agente de Trámites" in proc.stdout
        assert elapsed < _IMPORT_GRACE

    def test_list_tramites_muestra_catalogo(self):
        proc, _ = _run_cli(["--list-tramites"], timeout=_IMPORT_GRACE)
        assert proc.returncode == 0
        assert "curp" in proc.stdout
        assert "nss" in proc.stdout
        assert "Trámites disponibles" in proc.stdout


class TestCliValidacion:
    def test_curp_invalida_rechazada_con_error_claro(self):
        proc, _ = _run_cli(["--tramite", "curp", "--curp", "ABC123"], timeout=_IMPORT_GRACE)
        # argparse valida la CURP en el propio argumento
        assert proc.returncode == 2
        assert "CURP inválida" in proc.stderr

    def test_tramite_sin_curp_requerida(self):
        proc, _ = _run_cli(["--tramite", "nss"], timeout=_IMPORT_GRACE)
        assert proc.returncode != 0

    def test_version_inexistente_error_argparse(self):
        proc, _ = _run_cli(["--version"], timeout=_IMPORT_GRACE)
        assert proc.returncode == 2


class TestCliModoInteractivo:
    def test_salir_termina_limpio(self):
        """E2E del loop interactivo: 'salir' por stdin cierra sin colgarse."""
        proc, _ = _run_cli([], stdin="salir\n", timeout=_IMPORT_GRACE)
        assert proc.returncode == 0
        assert "Hasta luego" in proc.stdout

    def test_ayuda_dentro_del_loop(self):
        proc, _ = _run_cli([], stdin="ayuda\nsalir\n", timeout=_IMPORT_GRACE)
        assert proc.returncode == 0
