#!/usr/bin/env python3
"""
main_multimodal.py — Entry point multimodal.
Delega a src/main_multimodal.py (canonical).

Uso:
    python main_multimodal.py                    # Modo interactivo
    python main_multimodal.py --tramite curp     # Modo directo
    python main_multimodal.py --voice            # Modo voz
"""

import sys
from pathlib import Path

# Asegurar que src/ esté en el path (canonical)
_src_path = Path(__file__).parent / "src"
if _src_path.exists():
    sys.path.insert(0, str(_src_path))

if __name__ == "__main__":
    from src.main_multimodal import main as _main
    _main()
