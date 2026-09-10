"""Apertura de PDFs con el visor del sistema.

Extraído de src/tramites/base.py (incremento 2): lógica sin estado
que abre un PDF según la plataforma. Respeta el gate HEADLESS
(si headless=True no hace nada) y nunca lanza excepciones.
"""

import os
import platform
import subprocess
from pathlib import Path


def open_pdf(pdf_path: Path, headless: bool = False,
             on_debug=None, on_log=None, on_warn=None):
    """Abre PDF con visor predeterminado (solo si no es headless)."""
    if headless:
        if on_debug is not None:
            on_debug(f"Headless mode — omitiendo open_pdf: {pdf_path}")
        return
    try:
        sistema = platform.system()
        if sistema == "Windows":
            os.startfile(str(pdf_path))
        elif sistema == "Darwin":
            subprocess.run(["open", str(pdf_path)])
        else:
            subprocess.run(["xdg-open", str(pdf_path)])
        if on_log is not None:
            on_log("PDF abierto automáticamente")
    except Exception as e:
        if on_warn is not None:
            on_warn(f"No se pudo abrir PDF: {e}")
        if on_log is not None:
            on_log(f"Abrí manualmente: {pdf_path}")
