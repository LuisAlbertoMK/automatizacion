#!/usr/bin/env python3
"""
main.py — Entry point del Agente de Trámites GOB.MX.
Delega a src/main.py (canonical). Mantenido para compatibilidad.

Uso:
    python main.py                              # Modo interactivo
    python main.py --tramite curp --curp XXXX   # Directo
    python main.py --tramite nss --curp XXXX --correo a@b.com
    python main.py --perfil juan_garcia         # Con perfil guardado
"""

import sys
from pathlib import Path

# Asegurar que src/ esté en el path (canonical)
_src_path = Path(__file__).parent / "src"
if _src_path.exists():
    sys.path.insert(0, str(_src_path))

if __name__ == "__main__":
    from src.main import main as _main
    _main()
