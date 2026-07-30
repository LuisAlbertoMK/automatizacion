"""E2E NSS v4 — headed mode Firefox para bypass Incapsula."""
import asyncio


async def test_nss_headed():
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    CURP_FICTICIA = "GARC850101HDFRRN09"
    CORREO_FICTICIO = "test@example.com"

    print(f"Probando NSS HEADED + STEALTH + CURP: {CURP_FICTICIA}")
    print("=" * 60)

    stealth = Stealth()

    async with async_playwright() as p:
        # HEADED mode — sin headless
        browser = await p.firefox.launch(
            headless=False,
            firefox_user_prefs={
                "dom.webdriver.enabled": False,
                "useAutomationExtension": False,
                "media.navigator.enabled": True,
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

        # 1. GET portal
        print("1. Navegando a IMSS portal NSS (HEADED) ...")
        await page.goto(
            "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await page.wait_for_timeout(3000)
        html_get = await page.content()
        incapsula_get = "Incapsula" in html_get
        print(f"   URL: {page.url}")
        print(f"   Incapsula en GET: {incapsula_get}")

        if incapsula_get:
            # Esperar más — Incapsula a veces resuelve JS challenge
            print("   Esperando resolución de JS challenge (10s) ...")
            await page.wait_for_timeout(10000)
            html_get = await page.content()
            incapsula_get = "Incapsula" in html_get
            print(f"   Incapsula después de espera: {incapsula_get}")

        # 2. Llenar form
        print("2. Llenando formulario ...")
        curp_input = await page.query_selector("input[name='curp']")
        correo_input = await page.query_selector("input[name*='correo']")

        if not curp_input:
            print("   ERROR: input CURP no encontrado")
            # Guardar HTML para diagnóstico
            with open("output/e2e_nss_headed_noinput.html", "w", encoding="utf-8") as f:
                f.write(await page.content())
            await browser.close()
            return False

        await curp_input.fill(CURP_FICTICIA)
        if correo_input:
            await correo_input.fill(CORREO_FICTICIO)
        print("   OK")

        # 3. Submit
        print("3. Submit ...")
        continuar_btn = await page.query_selector("button:has-text('Continuar')")
        if not continuar_btn:
            continuar_btn = await page.query_selector("button[type='submit']")
        if continuar_btn:
            try:
                async with page.expect_navigation(timeout=15000):
                    await continuar_btn.click()
            except Exception:
                pass
        await page.wait_for_timeout(5000)
        print(f"   URL post: {page.url}")

        # 4. Resultado
        print("4. Analizando ...")
        html_post = await page.content()
        is_incapsula = "Incapsula" in html_post
        print(f"   Incapsula post-submit: {is_incapsula}")
        print(f"   HTML length: {len(html_post)}")

        with open("output/e2e_nss_headed.html", "w", encoding="utf-8") as f:
            f.write(html_post)

        if is_incapsula:
            print("   RESULTADO: Incapsula bloquea headed mode también")
        else:
            body = await page.inner_text("body")
            print(f"   ¡BYPASSED! Body length: {len(body)}")
            if body:
                print(f"   Preview: {body[:300]}")
            with open("output/e2e_nss_headed.txt", "w", encoding="utf-8") as f:
                f.write(body[:3000])

        await page.screenshot(path="output/e2e_nss_headed.png", full_page=True)
        await browser.close()

    return not is_incapsula


if __name__ == "__main__":
    asyncio.run(test_nss_headed())
