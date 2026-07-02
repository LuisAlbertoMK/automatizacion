"""Test CURP en vivo — verifica conectividad y consulta."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
os.environ["HEADLESS"] = "true"

async def test():
    from modules.curp import CURPModule
    m = CURPModule(captcha_solver=None, use_ocr=False)
    try:
        r = await m.consultar(curp="OOLL940914HMCRGS08")
        from pprint import pprint
        pprint(r)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
