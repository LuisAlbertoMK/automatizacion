#!/usr/bin/env python3
"""get_captcha.py - Con la MISMA config del NSS module"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="es-MX",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )

        print("Cargando portal IMSS...")
        resp = await page.goto(
            "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS",
            wait_until="domcontentloaded", timeout=30000
        )
        status = resp.status if resp else "N/A"
        print(f"Status: {status}, URL: {page.url}")
        await asyncio.sleep(5)

        body = await page.text_content("body") or ""
        print(f"\nBody ({len(body)} chars): {body[:400]}")
        if "Incapsula" in body:
            print("*** INCAPSULA ***")

        inputs = await page.query_selector_all("input")
        print(f"\nInputs encontrados: {len(inputs)}")
        for inp in inputs:
            name = (await inp.get_attribute("name")) or ""
            pid = (await inp.get_attribute("id")) or ""
            print(f"  name={name}, id={pid}")

        imgs = await page.query_selector_all("img")
        print(f"\nImagenes: {len(imgs)}")

        input("\nPresiona Enter para cerrar...")
        await browser.close()

asyncio.run(run())
