"""E2E funcional NSS v2 — con detección de URL post-submit."""
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
        print(f"   URL actual: {page.url}")

        # 2. Llenar formulario
        print("2. Llenando formulario ...")
        curp_input = await page.query_selector("input[name='curp']")
        correo_input = await page.query_selector("input[name*='correo']")
        
        if not curp_input:
            print("   ERROR: No se encontró input CURP")
            await browser.close()
            return False

        await curp_input.fill(CURP_FICTICIA)
        if correo_input:
            await correo_input.fill(CORREO_FICTICIO)
        print("   Formulario llenado OK")

        # 3. Click Continuar + esperar navegación
        print("3. Click en Continuar + esperando navegación ...")
        continuar_btn = await page.query_selector("button:has-text('Continuar')")
        if not continuar_btn:
            continuar_btn = await page.query_selector("button[type='submit']")
        if continuar_btn:
            # Esperar navegación post-click
            try:
                async with page.expect_navigation(timeout=15000):
                    await continuar_btn.click()
            except Exception:
                # Puede que no haya navegación, solo cambio dinámico
                pass
            print("   Click OK")
        else:
            print("   ERROR: No se encontró botón Continuar")
            await browser.close()
            return False

        await page.wait_for_timeout(5000)
        print(f"   URL post-submit: {page.url}")

        # 4. Capturar TODO el contenido (HTML + texto)
        print("4. Capturando contenido ...")
        
        # Screenshot
        await page.screenshot(path="output/e2e_nss_04_response_v2.png", full_page=True)
        
        # Texto visible
        body_text = await page.inner_text("body")
        print(f"   Body text length: {len(body_text)} chars")
        
        # HTML completo (para analizar después)
        html_content = await page.content()
        with open("output/e2e_nss_response_v2.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("   HTML guardado: output/e2e_nss_response_v2.html")

        # Texto visible
        with open("output/e2e_nss_response_v2.txt", "w", encoding="utf-8") as f:
            f.write(f"CURP: {CURP_FICTICIA}\n")
            f.write(f"Correo: {CORREO_FICTICIO}\n")
            f.write(f"URL final: {page.url}\n")
            f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n")
            f.write(body_text[:3000])
        print("   Texto guardado: output/e2e_nss_response_v2.txt")

        # Detectar indicadores en body_text Y html
        combined = (body_text + " " + html_content).lower()
        indicators = {
            "captcha": "captcha" in combined or "recaptcha" in combined,
            "error_msg": "error" in combined and ("no se" in combined or "inválido" in combined),
            "resultado": "nss" in combined and ("asignado" in combined or "resultado" in combined),
            "siguiente_paso": "continuar" in combined or "siguiente" in combined,
            "correo_invalido": "correo" in combined and ("inválido" in combined or "incorrecto" in combined),
            "curp_invalida": "curp" in combined and ("inválido" in combined or "incorrecto" in combined),
        }
        print("\n   Indicadores:")
        for k, v in indicators.items():
            print(f"     {k}: {'SI' if v else 'no'}")

        # Buscar mensajes de error visibles
        error_elements = await page.query_selector_all(".alert, .error, .mensaje, [class*='error'], [class*='alert'], [role='alert']")
        if error_elements:
            print(f"\n   Elementos de error/alerta encontrados: {len(error_elements)}")
            for i, el in enumerate(error_elements[:5]):
                text = await el.inner_text()
                print(f"     [{i}] {text[:100]}")

        await browser.close()

    print("\n" + "=" * 60)
    print("E2E NSS v2 COMPLETADO")
    return True


if __name__ == "__main__":
    asyncio.run(test_nss_submit())
