#!/usr/bin/env python3
"""
Test simple para verificar el portal CURP actual
"""
import asyncio
from playwright.async_api import async_playwright

async def test_curp():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("Navegando al portal CURP...")
        await page.goto("https://consultas.curp.gob.mx/CurpSP/gobmx/inicio.jsp", wait_until="networkidle")
        await asyncio.sleep(3)
        
        # Tomar screenshot
        await page.screenshot(path="portal_curp_screenshot.png")
        print("Screenshot guardado: portal_curp_screenshot.png")
        
        # Listar todos los inputs visibles
        print("\n=== INPUTS VISIBLES ===")
        inputs = await page.query_selector_all("input[type='text'], input:not([type])")
        for inp in inputs:
            visible = await inp.is_visible()
            if visible:
                name = await inp.get_attribute("name")
                id_attr = await inp.get_attribute("id")
                placeholder = await inp.get_attribute("placeholder")
                print(f"  name={name}, id={id_attr}, placeholder={placeholder}")
        
        # Esperar para inspección manual
        print("\nNavegador abierto. Presiona Ctrl+C para cerrar...")
        await asyncio.sleep(120)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_curp())
