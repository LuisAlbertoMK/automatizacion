#!/usr/bin/env python3
"""
main_multimodal.py
CLI principal con entrada multimodal (texto, voz, imagen)

Uso:
    python main_multimodal.py                    # Modo interactivo
    python main_multimodal.py --tramite curp     # Modo directo
    python main_multimodal.py --voice            # Modo voz
"""

import sys
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Cargar configuración
load_dotenv("config.env")

# Agregar path del proyecto
sys.path.insert(0, str(Path(__file__).parent))

from modules.orchestrator import TramitesOrchestrator


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Sistema de Automatización de Trámites GOB.MX con Entrada Multimodal"
    )
    
    parser.add_argument(
        "--tramite",
        choices=["curp", "nss", "antecedentes", "tenencia", "ambos"],
        help="Tipo de trámite a ejecutar"
    )
    
    parser.add_argument(
        "--mode",
        choices=["text", "voice", "image", "auto"],
        default="text",
        help="Modo de entrada (text, voice, image, auto)"
    )
    
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Usar entrada por voz (equivalente a --mode voice)"
    )
    
    parser.add_argument(
        "--curp",
        help="CURP (solo para modo texto directo)"
    )
    
    parser.add_argument(
        "--correo",
        help="Correo electrónico (solo para modo texto directo)"
    )
    
    parser.add_argument(
        "--placa",
        help="Placa vehicular (solo para modo texto directo)"
    )
    
    args = parser.parse_args()
    
    # Determinar modo de entrada
    if args.voice:
        modo = "voice"
    else:
        modo = args.mode
    
    # Crear orquestador
    orchestrator = TramitesOrchestrator()
    
    # Modo directo o interactivo
    if args.tramite:
        # Modo directo
        asyncio.run(orchestrator.ejecutar_tramite(args.tramite, modo))
    else:
        # Modo interactivo
        orchestrator.modo_interactivo()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Sistema cancelado por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n  Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
