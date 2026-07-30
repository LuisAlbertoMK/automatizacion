"""E2E funcional NSS — submit con CURP ficticia + screenshot + capturar respuesta."""
import asyncio
import time


async def test_nss_submit():
    from playwright.async_api import async_playwright

    CURP_FICTICIA = "GARC850101HDFRRN09"
    CORREO_FICTICIO = "test@example.com"

    print(f"Probando NSS con CURP: {CURP_FICTICIA}")
    print("=" * 60)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        # 1. Navegar al portal NSS
        print("1. Navegando a IMSS portal NSS ...")
        await page.goto(
            "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await page.wait_for_timeout(3000)

        await page.screenshot(path="output/e2e_nss_01_portal.png", full_page=False)
        print("   Screenshot: output/e2e_nss_01_portal.png")

        # 2. Verificar frames
        frames = page.frames
        print(f"2. Frames encontrados: {len(frames)}")
        for i, f in enumerate(frames):
            print(f"   Frame {i}: {f.url[:80]}")

        # 3. Buscar inputs
        print("3. Buscando campos del formulario ...")
        curp_input = await page.query_selector("input[name='curp']")
        correo_input = await page.query_selector("input[name*='correo']")
        
        if curp_input:
            print("   Input CURP: OK")
        else:
            print("   ERROR: No se encontró input CURP")
            await page.screenshot(path="output/e2e_nss_02_no_input.png")
            await browser.close()
            return False

        if correo_input:
            print("   Input Correo: OK")
        else:
            print("   WARNING: No se encontró input correo")

        # 4. Llenar formulario
        print("4. Llenando formulario ...")
        await curp_input.click()
        await curp_input.fill(CURP_FICTICIA)
        if correo_input:
            await correo_input.click()
            await correo_input.fill(CORREO_FICTICIO)
        print("   Formulario llenado OK")

        await page.screenshot(path="output/e2e_nss_02_filled.png")

        # 5. Click Continuar
        print("5. Haciendo click en Continuar ...")
        try:
            continuar_btn = await page.query_selector("button:has-text('Continuar')")
            if not continuar_btn:
                continuar_btn = await page.query_selector("button[type='submit']")
            if continuar_btn:
                await continuar_btn.click()
                print("   Click OK")
            else:
                print("   ERROR: No se encontró botón Continuar")
                await page.screenshot(path="output/e2e_nss_03_no_button.png")
                await browser.close()
                return False
        except Exception as e:
            print(f"   ERROR click: {e}")
            await page.screenshot(path="output/e2e_nss_03_error.png")
            await browser.close()
            return False

        # 6. Esperar respuesta
        print("6. Esperando respuesta (10s) ...")
        await page.wait_for_timeout(10000)

        await page.screenshot(path="output/e2e_nss_04_response.png", full_page=True)
        print("   Screenshot: output/e2e_nss_04_response.png")

        # 7. Capturar contenido
        print("7. Capturando contenido de respuesta ...")
        try:
            body_text = await page.inner_text("body")
            indicators = {
                "resultado": "resultado" in body_text.lower(),
                "no encontrado": "no se encontr" in body_text.lower(),
                "error": "error" in body_text.lower(),
                "captcha": "captcha" in body_text.lower() or "recaptcha" in body_text.lower(),
                "datos": "datos" in body_text.lower() or "nombre" in body_text.lower(),
                "continuar": "continuar" in body_text.lower(),
                "correo": "correo" in body_text.lower(),
            }
            print("   Indicadores detectados:")
            for k, v in indicators.items():
                print(f"     {k}: {'SI' if v else 'no'}")

            with open("output/e2e_nss_response.txt", "w", encoding="utf-8") as f:
                f.write(f"CURP: {CURP_FICTICIA}\n")
                f.write(f"Correo: {CORREO_FICTICIO}\n")
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Frames: {len(frames)}\n")
                f.write(f"Indicadores: {indicators}\n")
                f.write("=" * 60 + "\n")
                f.write(body_text[:2000])
            print("   Texto guardado: output/e2e_nss_response.txt")
        except Exception as e:
            print(f"   ERROR capturando texto: {e}")

        await browser.close()

    print("\n" + "=" * 60)
    print("E2E NSS COMPLETADO")
    print("Revisá los screenshots en output/e2e_nss_*.png")
    return True


if __name__ == "__main__":
    asyncio.run(test_nss_submit())
