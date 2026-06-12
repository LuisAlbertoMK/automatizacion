"""
download_captchas.py
Descarga automática de captchas IMSS desde el portal real.

Uso:
    py -3.14 download_captchas.py --count 500

Las imágenes se guardan en captcha_solver_imss/raw_captchas/ como UUID.jpg
Luego renombrás cada una como VALOR_esperado_UUID.jpg (ej: "CH7vnKC_a1b2c3d4.jpg")
y corrés el entrenamiento.

Requisitos:
    pip install playwright
    playwright install firefox
"""
import asyncio
import argparse
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from playwright.async_api import async_playwright

# ── Config ────────────────────────────────────────────────────────────────
PORTAL_URL = (
    "https://serviciosdigitales.imss.gob.mx/"
    "gestionAsegurados-web-externo/asignacionNSS"
)
OUTPUT_DIR = Path(__file__).resolve().parent / "captcha_solver_imss" / "raw_captchas"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# ── Helpers ───────────────────────────────────────────────────────────────

def _log(msg: str):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


async def find_captcha_img(page):
    """Busca el elemento img del captcha en la página."""
    selectors = [
        "img[src*='CaptchaServlet']",
        "img[src*='captchaServlet']",
        "img[src*='Captcha']",
        "img[src*='captcha']",
    ]
    for sel in selectors:
        img = await page.query_selector(sel)
        if img:
            return img
    return None


async def download_one_captcha(page) -> bool:
    """
    Toma screenshot del captcha actual y lo guarda.
    Returns True si se guardó correctamente.
    """
    captcha_img = await find_captcha_img(page)
    if not captcha_img:
        return False

    # Esperar que la imagen esté realmente cargada
    try:
        await captcha_img.wait_for_element_state("stable", timeout=8000)
    except Exception:
        pass  # seguir igual

    # Screenshot del elemento (evita Incapsula — usa cookies del browser)
    img_bytes = await captcha_img.screenshot()

    if not img_bytes or len(img_bytes) < 100:
        return False

    # Guardar con UUID
    fname = f"{uuid.uuid4().hex[:12]}.jpg"
    path = OUTPUT_DIR / fname
    path.write_bytes(img_bytes)
    return True


async def refresh_captcha(page) -> bool:
    """
    Intenta refrescar el captcha SIN recargar toda la página.
    Estrategias:
      1. Hacer clic en la imagen (a veces refresca)
      2. Recargar el src con un cache-buster
      3. Fallback: recargar página
    """
    # Estrategia 1: clic en la imagen (algunos portales refrescan así)
    captcha_img = await find_captcha_img(page)
    if captcha_img:
        try:
            await captcha_img.click()
            await asyncio.sleep(1.5)
            return True
        except Exception:
            pass

    # Estrategia 2: recargar src con cache buster
    if captcha_img:
        src = await captcha_img.get_attribute("src")
        if src:
            try:
                # Agregar timestamp para evitar caché
                separator = "&" if "?" in src else "?"
                new_src = f"{src}{separator}_{int(time.time()*1000)}"
                import json
                new_src_safe = json.dumps(new_src)
                await page.evaluate(f"arguments[0].src = {new_src_safe}", captcha_img)
                await asyncio.sleep(1.5)
                return True
            except Exception:
                pass

    # Estrategia 3: recargar página (fallback)
    _log("  Recargando página...")
    try:
        await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        return True
    except Exception as e:
        _log(f"  Error recargando: {e}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Descarga captchas IMSS")
    parser.add_argument("--count", type=int, default=100,
                        help="Cuantos captchas descargar (default: 100)")
    parser.add_argument("--headless", action="store_true",
                        help="Modo headless (sin ventana)")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Delay entre captchas en segundos (default: 3.0)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Contar archivos existentes
    existing = len(list(OUTPUT_DIR.glob("*.jpg")))
    if existing > 0:
        _log(f"YA HAY {existing} captchas en {OUTPUT_DIR}")
        _log("Continuando descarga (los archivos existentes se mantienen)...")

    _log(f"Iniciando descarga de {args.count} captchas IMSS...")
    _log(f"Directorio: {OUTPUT_DIR}")
    _log(f"Delay: {args.delay}s | Headless: {args.headless}")
    _log("")

    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=args.headless)

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=USER_AGENT,
            locale="es-MX",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )

        # ── Cargar portal ──────────────────────────────────────
        _log("Cargando portal IMSS...")
        try:
            resp = await page.goto(
                PORTAL_URL,
                wait_until="domcontentloaded",
                timeout=30000,
            )
        except Exception as e:
            _log(f"ERROR cargando portal: {e}")
            await browser.close()
            sys.exit(1)

        status = resp.status if resp else "N/A"
        _log(f"Status: {status} | URL: {page.url}")

        # Verificar si Incapsula nos bloqueó
        body_text = await page.text_content("body") or ""
        if "Incapsula" in body_text:
            _log("⚠  BLOQUEADO POR INCAPSULA")
            _log("Abriendo Firefox visible para resolver el challenge...")
            await page.screenshot(path=OUTPUT_DIR / "_incapsula.png")
            _log(f"Screenshot guardado en {OUTPUT_DIR / '_incapsula.png'}")
            _log("Resolve el captcha de Incapsula en la ventana de Firefox")
            _log("Esperando hasta 60 segundos...")
            for i in range(60):
                await asyncio.sleep(1)
                body_text = await page.text_content("body") or ""
                if "Incapsula" not in body_text:
                    _log("[OK] Incapsula resuelto!")
                    break
                if i % 10 == 9:
                    _log(f"  Esperando... {i+1}s")
            else:
                _log("✗ No se pudo resolver Incapsula")
                await browser.close()
                sys.exit(1)

        # ── Loop de descarga ───────────────────────────────────
        downloaded = 0
        errors = 0
        start_time = time.time()

        # Intentar primer captcha
        if not await download_one_captcha(page):
            _log("ERROR: No se encontró captcha en la página")
            _log("Posibles causas:")
            _log("  - La página aún no terminó de cargar")
            _log("  - El selector del captcha cambió")
            _log("  - Incapsula bloquea")
            _log(f"\nScreenshot guardado en {OUTPUT_DIR / '_debug.png'}")
            await page.screenshot(path=str(OUTPUT_DIR / "_debug.png"))
            await browser.close()
            sys.exit(1)

        downloaded += 1
        _log(f"[1/{args.count}] OK [OK]")

        while downloaded < args.count:
            # Refrescar captcha
            if not await refresh_captcha(page):
                errors += 1
                _log(f"  Error refrescando (error #{errors})")
                if errors >= 5:
                    _log("Demasiados errores seguidos, abortando")
                    break
                await asyncio.sleep(5)
                continue

            errors = 0  # reset

            # Esperar que cargue el nuevo captcha
            await asyncio.sleep(1.5)

            # Descargar
            if await download_one_captcha(page):
                downloaded += 1
                if downloaded % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = downloaded / elapsed
                    _log(f"[{downloaded}/{args.count}] OK [OK] "
                         f"({rate:.1f} captchas/min, {elapsed:.0f}s)")
                elif downloaded <= 5 or downloaded == args.count:
                    _log(f"[{downloaded}/{args.count}] OK [OK]")
            else:
                _log(f"  No se encontró captcha en el refresh")

            # Delay entre captchas (evitar rate limiting)
            await asyncio.sleep(args.delay)

        # ── Resumen ────────────────────────────────────────────
        elapsed = time.time() - start_time
        total_files = len(list(OUTPUT_DIR.glob("*.jpg")))
        _log("")
        _log(f"{'='*60}")
        _log(f"DESCARGA COMPLETADA")
        _log(f"  Descargados: {downloaded}")
        _log(f"  Archivos en dir: {total_files}")
        _log(f"  Tiempo total: {elapsed:.0f}s ({elapsed/60:.1f}min)")
        _log(f"  Rate: {downloaded/elapsed:.2f} captchas/s")
        _log(f"")
        _log(f"  SIGUIENTE PASO:")
        _log(f"  1. Andá a {OUTPUT_DIR}")
        _log(f"  2. Renombrá cada archivo como:")
        _log(f"       VALOR_UUID.jpg")
        _log(f"     (ej: '2kypRJK_a1b2c3d4e5f6.jpg')")
        _log(f"  3. Corré: py -3.14 -m captcha_solver_imss.cnn_solver.train_v3")
        _log(f"{'='*60}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
