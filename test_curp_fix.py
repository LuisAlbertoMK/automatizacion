#!/usr/bin/env python3
"""
Test rápido del módulo CURP corregido
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("config.env")

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from modules.curp import CURPModule

async def test():
    print("=== TEST MÓDULO CURP ===\n")
    
    curp_test = "OOLL940914HMCRGS08"
    
    modulo = CURPModule(captcha_solver=None)
    
    try:
        resultado = await modulo.consultar(curp=curp_test)
        print("\n=== RESULTADO ===")
        for k, v in resultado.items():
            print(f"{k}: {v}")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
