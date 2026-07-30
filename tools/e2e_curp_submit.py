"""E2E funcional CURP — submit con CURP ficticia + screenshot + capturar respuesta."""
import asyncio
import time


async def test_curp_submit():
    from playwright.async_api import async_playwright

    # CURP ficticia válida en formato (no tiene datos reales)
    # HXXX000101HDFLRL09 (formato correcto: 4 apellido + 2 nombre + 6 fecha + H + 2 estado + 3 conson + 2 disamb + 1 check)
    CURP_FICTICIA = "GARC850101HDFRRN09"

    print(f"Probando CURP: {CURP_FICTICIA}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        # 1. Navegar al portal
        print("1. Navegando a gob.mx/curp ...")
        await page.goto("https://www.gob.mx/curp", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Screenshot inicial
        await page.screenshot(path="output/e2e_curp_01_portal.png", full_page=False)
        print("   Screenshot: output/e2e_curp_01_portal.png")

        # 2. Verificar iframe (CURP suele estar en iframe)
        frames = page.frames
        print(f"2. Frames encontrados: {len(frames)}")
        for i, f in enumerate(frames):
            print(f"   Frame {i}: {f.url[:80]}")

        # Buscar input en frames
        target_frame = page
        for f in frames:
            try:
                inp = await f.query_selector("input[name='curp']")
                if inp:
                    target_frame = f
                    print(f"   Input CURP encontrado en frame: {f.url[:60]}")
                    break
            except Exception:
                pass

        # 3. Llenar CURP
        print("3. Llenando campo CURP ...")
        try:
            curp_input = await target_frame.query_selector("input[name='curp']")
            if not curp_input:
                # Intentar otros selectores
                curp_input = await target_frame.query_selector("input[type='text']")
            if curp_input:
                await curp_input.click()
                await curp_input.fill(CURP_FICTICIA)
                print("   Campo llenado OK")
            else:
                print("   ERROR: No se encontró input de CURP")
                await page.screenshot(path="output/e2e_curp_02_no_input.png")
                await browser.close()
                return False
        except Exception as e:
            print(f"   ERROR llenando campo: {e}")
            await page.screenshot(path="output/e2e_curp_02_error.png")
            await browser.close()
            return False

        # Screenshot después de llenar
        await page.screenshot(path="output/e2e_curp_02_filled.png")

        # 4. Click Buscar
        print("4. Haciendo click en Buscar ...")
        try:
            buscar_btn = await target_frame.query_selector("button:has-text('Buscar')")
            if not buscar_btn:
                buscar_btn = await target_frame.query_selector("button[type='submit']")
            if not buscar_btn:
                buscar_btn = await target_frame.query_selector("input[type='submit']")
            if buscar_btn:
                await buscar_btn.click()
                print("   Click OK")
            else:
                print("   ERROR: No se encontró botón Buscar")
                await page.screenshot(path="output/e2e_curp_03_no_button.png")
                await browser.close()
                return False
        except Exception as e:
            print(f"   ERROR click: {e}")
            await page.screenshot(path="output/e2e_curp_03_error.png")
            await browser.close()
            return False

        # 5. Esperar respuesta (portal puede ser lento)
        print("5. Esperando respuesta (10s) ...")
        await page.wait_for_timeout(10000)

        # Screenshot respuesta
        await page.screenshot(path="output/e2e_curp_04_response.png", full_page=True)
        print("   Screenshot: output/e2e_curp_04_response.png")

        # 6. Capturar texto de la página
        print("6. Capturando contenido de respuesta ...")
        try:
            body_text = await target_frame.inner_text("body")
            # Buscar indicadores de respuesta
            indicators = {
                "resultado": "resultado" in body_text.lower(),
                "no encontrado": "no se encontr" in body_text.lower(),
                "error": "error" in body_text.lower(),
                "captcha": "captcha" in body_text.lower() or "recaptcha" in body_text.lower(),
                "datos": "datos" in body_text.lower() or "nombre" in body_text.lower(),
            }
            print("   Indicadores detectados:")
            for k, v in indicators.items():
                print(f"     {k}: {'SI' if v else 'no'}")

            # Guardar texto relevante (primeros 2000 chars)
            with open("output/e2e_curp_response.txt", "w", encoding="utf-8") as f:
                f.write(f"CURP: {CURP_FICTICIA}\n")
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Frames: {len(frames)}\n")
                f.write(f"Indicadores: {indicators}\n")
                f.write("=" * 60 + "\n")
                f.write(body_text[:2000])
            print("   Texto guardado: output/e2e_curp_response.txt")
        except Exception as e:
            print(f"   ERROR capturando texto: {e}")

        await browser.close()

    print("\n" + "=" * 60)
    print("E2E CURP COMPLETADO")
    print("Revisá los screenshots en output/e2e_curp_*.png")
    return True


if __name__ == "__main__":
    asyncio.run(test_curp_submit())
