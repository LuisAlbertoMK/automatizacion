"""
e2e_curp_check.py
E2E structural verification of CURP portal against module selectors.
Opens the real gob.mx/curp portal and checks if selectors from curp.py match.

Does NOT submit any CURP — only verifies form structure.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


PORTAL_URL = "https://www.gob.mx/curp/"
PORTAL_CONSULTA_URL = "https://consultas.curp.gob.mx/CurpSP/"

# Selectors from curp.py
CURP_INPUT_SELECTORS = [
    "input[name='curp']",
    "input[id='curp']",
    "input[id='txtCurp']",
    "input[name='txtCurp']",
    "input[placeholder*='CURP']",
    "input[placeholder*='curp']",
    "input[maxlength='18']",
    "input[type='text'][maxlength='18']",
]

SUBMIT_BUTTON_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Buscar')",
    "button:has-text('Consultar')",
    "a:has-text('Buscar')",
    "#btnBuscar",
    "button.btn.btn-primary",
    "button[onclick*='buscar']",
]

CAPTCHA_IMG_SELECTORS = [
    "img[src*='captcha']",
    "img[id*='captcha']",
    "img[src*='Captcha']",
    ".captcha img",
]

TAB_SELECTORS = [
    "a[href*='porCurp']",
    "a[href*='curp']",
    "input[value='Por CURP']",
    "a:has-text('Por CURP')",
    "a:has-text('CURP')",
    "button:has-text('CURP')",
    "#consultaCurp",
    ".tab-curp",
    "li:has-text('CURP')",
    "[onclick*='curp']",
]


async def check_portal():
    from playwright.async_api import async_playwright

    print("=" * 70)
    print("  E2E CURP Portal Structural Check")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
            viewport={"width": 1280, "height": 720},
        )
        page = await context.new_page()

        # ── 1. Load primary URL ──
        print(f"\n  [1] Loading {PORTAL_URL} ...")
        t0 = time.time()
        try:
            resp = await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30000)
            load_ms = int((time.time() - t0) * 1000)
            print(f"      HTTP {resp.status} — {load_ms}ms")
        except Exception as e:
            print(f"      ERROR: {e}")
            # Try fallback
            print(f"\n  [1b] Trying fallback {PORTAL_CONSULTA_URL} ...")
            t0 = time.time()
            try:
                resp = await page.goto(PORTAL_CONSULTA_URL, wait_until="domcontentloaded", timeout=30000)
                load_ms = int((time.time() - t0) * 1000)
                print(f"      HTTP {resp.status} — {load_ms}ms")
            except Exception as e2:
                print(f"      Fallback also failed: {e2}")
                await browser.close()
                return

        # ── 2. Screenshot ──
        screenshot_path = str(Path(__file__).resolve().parent.parent / "output" / "e2e_curp_portal.png")
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
        for inp in all_inputs[:15]:
            name = await inp.get_attribute("name") or ""
            id_ = await inp.get_attribute("id") or ""
            type_ = await inp.get_attribute("type") or ""
            placeholder = await inp.get_attribute("placeholder") or ""
            maxlength = await inp.get_attribute("maxlength") or ""
            visible = await inp.is_visible()
            print(f"      name={name:20s} id={id_:20s} type={type_:10s} "
                  f"placeholder={placeholder:20s} maxlength={maxlength:5s} visible={visible}")

        # ── 5. Check all buttons ──
        all_buttons = await page.query_selector_all("button, input[type='submit'], a.btn")
        print(f"\n  [5] All buttons/links: {len(all_buttons)}")
        for btn in all_buttons[:10]:
            text = (await btn.inner_text()).strip()[:30] if await btn.is_visible() else "(hidden)"
            tag = await btn.evaluate("el => el.tagName")
            cls = await btn.get_attribute("class") or ""
            print(f"      [{tag}] text='{text}' class={cls[:40]}")

        # ── 6. Check CURP input selectors ──
        print("\n  [6] CURP input selector matching:")
        matched_curp = False
        for sel in CURP_INPUT_SELECTORS:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    visible = await page.locator(sel).first.is_visible()
                    print(f"      MATCH: {sel} — count={count}, visible={visible}")
                    matched_curp = True
            except Exception:
                pass
        if not matched_curp:
            print("      NO MATCH for any CURP input selector")

        # ── 7. Check submit buttons ──
        print("\n  [7] Submit button selector matching:")
        matched_submit = False
        for sel in SUBMIT_BUTTON_SELECTORS:
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
            print("      NO MATCH for any submit button selector")

        # ── 8. Check captcha ──
        print("\n  [8] Captcha selector matching:")
        matched_captcha = False
        for sel in CAPTCHA_IMG_SELECTORS:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    print(f"      MATCH: {sel} — count={count}")
                    matched_captcha = True
            except Exception:
                pass
        if not matched_captcha:
            print("      NO CAPTCHA IMAGE found (may appear after filling form)")

        # ── 9. Check tabs ──
        print("\n  [9] Tab 'Por CURP' selector matching:")
        matched_tab = False
        for sel in TAB_SELECTORS:
            try:
                count = await page.locator(sel).count()
                if count > 0:
                    visible = await page.locator(sel).first.is_visible()
                    print(f"      MATCH: {sel} — count={count}, visible={visible}")
                    matched_tab = True
            except Exception:
                pass
        if not matched_tab:
            print("      NO TAB MATCH found")

        # ── Summary ──
        print(f"\n{'=' * 70}")
        print("  SUMMARY:")
        print(f"    CURP input:   {'OK' if matched_curp else 'MISSING'}")
        print(f"    Submit button: {'OK' if matched_submit else 'MISSING'}")
        print(f"    Captcha image: {'OK' if matched_captcha else 'Not yet visible (normal)'}")
        print(f"    Tab CURP:      {'OK' if matched_tab else 'MISSING'}")
        print(f"{'=' * 70}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(check_portal())
