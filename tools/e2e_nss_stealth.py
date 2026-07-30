"""E2E NSS v3 — con playwright-stealth para bypass Incapsula."""
import asyncio


async def test_nss_stealth():
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    CURP_FICTICIA = "GARC850101HDFRRN09"
    CORREO_FICTICIO = "test@example.com"

    print(f"Probando NSS con STEALTH + CURP: {CURP_FICTICIA}")
    print("=" * 60)

    stealth = Stealth()

    async with async_playwright() as p:
        # Lanzar Firefox con stealth patches
        browser = await p.firefox.launch(
            headless=True,
            firefox_user_prefs={
                "dom.webdriver.enabled": False,
                "useAutomationExtension": False,
            },
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
            locale="es-MX",
            timezone_id="America/Mexico_City",
        )
        await stealth.apply_stealth_async(context)

        page = await context.new_page()

        # 1. Navegar al portal NSS
        print("1. Navegando a IMSS portal NSS (con stealth) ...")
        await page.goto(
            "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await page.wait_for_timeout(3000)
        print(f"   URL: {page.url}")

        # Verificar que no Incapsula en GET
        html_get = await page.content()
        if "Incapsula" in html_get:
            print("   WARNING: Incapsula detectada en GET (pre-form)")
        else:
            print("   GET limpio — sin Incapsula")

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

        # 3. Click Continuar
        print("3. Click en Continuar ...")
        continuar_btn = await page.query_selector("button:has-text('Continuar')")
        if not continuar_btn:
            continuar_btn = await page.query_selector("button[type='submit']")
        if continuar_btn:
            try:
                async with page.expect_navigation(timeout=15000):
                    await continuar_btn.click()
            except Exception:
                pass
            print("   Click OK")
        else:
            print("   ERROR: No se encontró botón Continuar")
            await browser.close()
            return False

        await page.wait_for_timeout(5000)
        print(f"   URL post-submit: {page.url}")

        # 4. Analizar respuesta
        print("4. Analizando respuesta ...")
        html_post = await page.content()
        body_text = await page.inner_text("body")

        is_incapsula = "Incapsula" in html_post or "Incapsula" in body_text
        print(f"   Incapsula detectada: {is_incapsula}")
        print(f"   HTML length: {len(html_post)} chars")
        print(f"   Body text length: {len(body_text)} chars")

        if is_incapsula:
            # Extraer incident ID
            import re
            incident = re.search(r"incident.?id[:\s]*(\d[\d-]+)", html_post, re.IGNORECASE)
            if incident:
                print(f"   Incident ID: {incident.group(1)}")
            print("   RESULTADO: Incapsula SIGUE bloqueando con stealth")
        else:
            print("   RESULTADO: ¡Incapsula BYPASSED!")
            if body_text:
                print(f"   Primeros 200 chars: {body_text[:200]}")

        # Guardar evidencia
        with open("output/e2e_nss_stealth.html", "w", encoding="utf-8") as f:
            f.write(html_post)
        with open("output/e2e_nss_stealth.txt", "w", encoding="utf-8") as f:
            f.write("Stealth: playwright-stealth\n")
            f.write(f"URL: {page.url}\n")
            f.write(f"Incapsula: {is_incapsula}\n")
            f.write(f"Body length: {len(body_text)}\n")
            f.write("=" * 60 + "\n")
            f.write(body_text[:3000])

        await page.screenshot(path="output/e2e_nss_stealth.png", full_page=True)

        await browser.close()

    print("\n" + "=" * 60)
    print("E2E NSS STEALTH COMPLETADO")
    if is_incapsula:
        print("Incapsula sigue activo — probando headed mode como siguiente intento")
    return not is_incapsula


if __name__ == "__main__":
    asyncio.run(test_nss_stealth())
