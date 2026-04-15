#!/usr/bin/env python3
"""
Test del módulo NSS (IMSS)
"""
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("config.env")

sys.path.insert(0, str(Path(__file__).parent))

from modules.nss import NSSModule

async def test():
    print("=== TEST MÓDULO NSS (IMSS) ===\n")
    
    curp_test = input("Ingresa CURP (18 caracteres): ").strip().upper()
    correo_test = input("Ingresa correo electrónico: ").strip()
    
    if not curp_test or not correo_test:
        print("Error: CURP y correo son requeridos")
        return
    
    modulo = NSSModule(captcha_solver=None, mail_reader=None)
    
    try:
        resultado = await modulo.consultar(curp=curp_test, correo=correo_test)
        print("\n=== RESULTADO ===")
        for k, v in resultado.items():
            print(f"{k}: {v}")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
