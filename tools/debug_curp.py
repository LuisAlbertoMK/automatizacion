#!/usr/bin/env python3
"""
Script de depuración para inspeccionar el portal CURP
"""
import asyncio
from playwright.async_api import async_playwright

PORTAL_URL = "https://consultas.curp.gob.mx/CurpSP/gobmx/default.jsp"

async def inspect_portal():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=1000)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="es-MX",
        )
        page = await context.new_page()
        
        print("Abriendo portal CURP...")
        await page.goto(PORTAL_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        
        print("\n=== INSPECCIONANDO ESTRUCTURA DEL PORTAL ===\n")
        
        # Obtener todo el HTML
        content = await page.content()
        
        # Buscar inputs
        print("--- INPUTS ENCONTRADOS ---")
        inputs = await page.query_selector_all("input")
        for i, inp in enumerate(inputs):
            inp_type = await inp.get_attribute("type") or "text"
            inp_name = await inp.get_attribute("name") or ""
            inp_id = await inp.get_attribute("id") or ""
            inp_placeholder = await inp.get_attribute("placeholder") or ""
            inp_value = await inp.get_attribute("value") or ""
            
            print(f"{i+1}. type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}, value={inp_value}")
        
        # Buscar botones y links
        print("\n--- BOTONES Y ENLACES ---")
        buttons = await page.query_selector_all("button, a[href], input[type='submit'], input[type='button']")
        for i, btn in enumerate(buttons[:20]):  # Limitar a 20
            tag = await btn.evaluate("el => el.tagName")
            text = (await btn.text_content() or "").strip()[:50]
            href = await btn.get_attribute("href") or ""
            btn_type = await btn.get_attribute("type") or ""
            onclick = await btn.get_attribute("onclick") or ""
            
            if text or href or onclick:
                print(f"{i+1}. <{tag}> text='{text}', href={href}, type={btn_type}, onclick={onclick[:50]}")
        
        # Buscar selects
        print("\n--- SELECTS ENCONTRADOS ---")
        selects = await page.query_selector_all("select")
        for i, sel in enumerate(selects):
            sel_name = await sel.get_attribute("name") or ""
            sel_id = await sel.get_attribute("id") or ""
            print(f"{i+1}. name={sel_name}, id={sel_id}")
        
        # Buscar imágenes (posibles captchas)
        print("\n--- IMÁGENES (posibles CAPTCHA) ---")
        images = await page.query_selector_all("img")
        for i, img in enumerate(images):
            src = await img.get_attribute("src") or ""
            img_id = await img.get_attribute("id") or ""
            alt = await img.get_attribute("alt") or ""
            if "captcha" in src.lower() or "captcha" in img_id.lower():
                print(f"{i+1}. CAPTCHA: src={src}, id={img_id}, alt={alt}")
        
        print("\n\n=== ESPERANDO PARA INSPECCIÓN MANUAL ===")
        print("Inspecciona el navegador manualmente.")
        print("Presiona Enter aquí cuando termines...")
        
        # Mantener el navegador abierto
        await asyncio.sleep(300)  # 5 minutos
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect_portal())
