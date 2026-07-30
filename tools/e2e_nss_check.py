"""
e2e_nss_check.py
E2E structural verification of NSS (IMSS) portal against module selectors.
Does NOT submit — only verifies form structure.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


PORTAL_URL = "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS"


async def check_portal():
    from playwright.async_api import async_playwright

    print("=" * 70)
    print("  E2E NSS Portal Structural Check")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        # ── 1. Load portal ──
        print(f"\n  [1] Loading {PORTAL_URL} ...")
        t0 = time.time()
        try:
            resp = await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30000)
            load_ms = int((time.time() - t0) * 1000)
            print(f"      HTTP {resp.status} — {load_ms}ms")
        except Exception as e:
            print(f"      ERROR: {e}")
            await browser.close()
            return

        # Wait for JS to render
        await page.wait_for_timeout(3000)

        # ── 2. Screenshot ──
        screenshot_path = str(Path(__file__).resolve().parent.parent / "output" / "e2e_nss_portal.png")
        Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n  [2] Screenshot: {screenshot_path}")

        # ── 3. Page title and URL ──
        title = await page.title()
        url = page.url
        print(f"\n  [3] Title: {title}")
        print(f"      URL: {url}")

        # ── 4. Check all input fields on page ──
        all_inputs = await page.query_selector_all("input")
        print(f"\n  [4] All inputs on page: {len(all_inputs)}")
        for inp in all_inputs[:20]:
            name = await inp.get_attribute("name") or ""
            id_ = await inp.get_attribute("id") or ""
            type_ = await inp.get_attribute("type") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            visible = await inp.is_visible()
            print(f"      name={name:25s} id={id_:25s} type={type_:10s} "
                  f"placeholder={placeholder:30s} visible={visible}")

        # ── 5. Check all buttons ──
        all_buttons = await page.query_selector_all("button, input[type='submit'], a.btn")
        print(f"\n  [5] All buttons/links: {len(all_buttons)}")
        for btn in all_buttons[:15]:
            text = ""
            try:
                text = (await btn.inner_text()).strip()[:30]
            except Exception:
                text = "(no text)"
            tag = await btn.evaluate("el => el.tagName")
            cls = await btn.get_attribute("class") or ""
            visible = await btn.is_visible()
            print(f"      [{tag}] text='{text}' class={cls[:40]} visible={visible}")

        # ── 6. Check CURP input selectors (from nss.py) ──
        curp_selectors = [
            "input[name*='curp']",
            "input[id*='curp']",
            "#curp",
            "input[placeholder*='CURP']",
            "input[placeholder*='curp']",
        ]
        print("\n  [6] CURP input selector matching:")
        matched_curp = False
        for sel in curp_selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    visible = await page.locator(sel).first.is_visible()
                    print(f"      MATCH: {sel} — count={count}, visible={visible}")
                    matched_curp = True
            except Exception:
                pass
        if not matched_curp:
            print("      NO MATCH for CURP input selectors")

        # ── 7. Check email input selectors ──
        email_selectors = [
            "input[type='email']",
            "input[name*='correo']",
            "input[name*='email']",
            "input[placeholder*='correo']",
            "input[placeholder*='email']",
            "input[name*='mail']",
        ]
        print("\n  [7] Email input selector matching:")
        matched_email = False
        for sel in email_selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    visible = await page.locator(sel).first.is_visible()
                    print(f"      MATCH: {sel} — count={count}, visible={visible}")
                    matched_email = True
            except Exception:
                pass
        if not matched_email:
            print("      NO MATCH for email input selectors")

        # ── 8. Check submit buttons ──
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Consultar')",
            "button:has-text('Buscar')",
            "button:has-text('Obtener')",
            "a:has-text('Consultar')",
            "#btnBuscar",
            "#btnConsultar",
        ]
        print("\n  [8] Submit button selector matching:")
        matched_submit = False
        for sel in submit_selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    visible = await page.locator(sel).first.is_visible()
                    text = await page.locator(sel).first.inner_text() if visible else "(hidden)"
                    print(f"      MATCH: {sel} — count={count}, visible={visible}, text='{text.strip()[:20]}'")
                    matched_submit = True
            except Exception:
                pass
        if not matched_submit:
            print("      NO MATCH for submit button selectors")

        # ── 9. Check captcha (reCAPTCHA) ──
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            ".g-recaptcha",
            "#recaptcha",
            "iframe[title*='reCAPTCHA']",
            "img[src*='captcha']",
        ]
        print("\n  [9] Captcha/reCAPTCHA selector matching:")
        matched_captcha = False
        for sel in captcha_selectors:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    print(f"      MATCH: {sel} — count={count}")
                    matched_captcha = True
            except Exception:
                pass
        if not matched_captcha:
            print("      NO CAPTCHA found")

        # ── Summary ──
        print(f"\n{'=' * 70}")
        print("  SUMMARY:")
        print(f"    CURP input:    {'OK' if matched_curp else 'MISSING'}")
        print(f"    Email input:   {'OK' if matched_email else 'MISSING'}")
        print(f"    Submit button: {'OK' if matched_submit else 'MISSING'}")
        print(f"    Captcha:       {'OK' if matched_captcha else 'Not found (may be JS-loaded)'}")
        print(f"{'=' * 70}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(check_portal())
