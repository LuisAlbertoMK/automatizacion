"""
modules/base.py
Clase base para todos los módulos de trámites.
Centraliza: selectors, captcha, PDF, logging, browser lifecycle.
"""
import os, re, time, asyncio, json, subprocess, platform
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PwTimeout

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
TIMEOUT = int(os.getenv("TIMEOUT", "60")) * 1000
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


class BaseModule:
    """
    Clase base para módulos de trámites.

    Provee:
      - Browser lifecycle (lanzar FireFox con anti-detección)
      - Fill fields con múltiples selectores (fill_field)
      - Click con múltiples selectores (click_first)
      - Resolver CAPTCHA de imagen (resolve_image_captcha)
      - Esperar reCAPTCHA manual (wait_for_recaptcha)
      - Detectar site_key de reCAPTCHA (detect_site_key)
      - Inyectar token reCAPTCHA (inject_recaptcha_token)
      - Descargar PDF (download_pdf)
      - Abrir PDF (open_pdf)
      - Logging unificado (log, debug, warn, error)
      - Screenshot de debug (debug_screenshot)
    """

    def __init__(self, captcha_solver=None, use_ocr=True, name="Base"):
        self.solver = captcha_solver
        self.name = name
        self.use_ocr = use_ocr
        self.ocr = None
        if use_ocr:
            try:
                from utils.ocr import OCRExtractor
                self.ocr = OCRExtractor()
            except ImportError:
                pass

    async def launch_browser(self):
        """Lanza browser con configuración anti-detección."""
        p = await async_playwright().__aenter__()
        browser = await p.firefox.launch(headless=HEADLESS)
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
        return p, browser, page

    async def close_browser(self, p, browser):
        """Cierra browser y playwright."""
        try:
            await browser.close()
        except Exception:
            pass
        try:
            await p.__aexit__(None, None, None)
        except Exception:
            pass

    async def goto(self, page: Page, url: str, fallback_url: str = None):
        """Navega a URL con fallback."""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
        except Exception:
            if fallback_url:
                await page.goto(fallback_url, wait_until="domcontentloaded", timeout=TIMEOUT)
        await asyncio.sleep(2)

    async def fill_field(self, page: Page, selectors: list, value: str) -> bool:
        """Llena un campo probando múltiples selectores. Retorna True si encontró alguno."""
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    self.debug(f"Llenando campo con selector: {sel}")
                    await loc.first.fill(value)
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                continue
        return False

    async def click_first(self, page: Page, selectors: list, wait_nav: bool = False, timeout_nav: int = 30000) -> bool:
        """Hace clic en el primer selector visible. Retorna True si encontró."""
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    self.debug(f"Haciendo clic: {sel}")
                    if wait_nav:
                        async with page.expect_navigation(timeout=timeout_nav):
                            await loc.first.click()
                        await asyncio.sleep(1)
                    else:
                        await loc.first.click()
                        await asyncio.sleep(1)
                    return True
            except PwTimeout:
                self.debug(f"Navigation timeout en {sel}, continuando...")
                return True
            except Exception:
                continue
        return False

    async def resolve_image_captcha(self, page: Page, img_selectors: list, input_selectors: list,
                                     numeric: bool = True, captcha_name: str = "captcha") -> bool:
        """Detecta y resuelve CAPTCHA de imagen. Retorna True si lo resolvió."""
        import requests as reqs

        captcha_img = None
        for sel in img_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                captcha_img = loc.first
                break

        if not captcha_img:
            self.log("Sin CAPTCHA de imagen detectado")
            return False

        self.log(f"CAPTCHA de imagen detectado, descargando...")

        # Obtener src de la imagen
        src = await captcha_img.get_attribute("src")
        if not src:
            return False

        if src.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(page.url)
            src = f"{parsed.scheme}://{parsed.netloc}{src}"

        try:
            resp = reqs.get(src, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            img_bytes = resp.content
        except Exception as e:
            self.warn(f"Error descargando CAPTCHA: {e}")
            return False

        solution = None
        if self.solver:
            try:
                solution = self.solver.solve_image(img_bytes, numeric=numeric)
                self.log(f"CAPTCHA resuelto: {solution}")
            except Exception as e:
                self.warn(f"Solver falló: {e}")

        if not solution:
            solution = os.getenv("CAPTCHA_VALUE", "").strip()
            if solution:
                self.log(f"CAPTCHA desde variable de entorno")

        if not solution:
            self.warn("Sin solución de CAPTCHA")
            return False

        return await self.fill_field(page, input_selectors, solution)

    async def wait_for_recaptcha(self, page: Page, max_wait: int = 120, module_name: str = ""):
        """Espera a que el usuario resuelva reCAPTCHA manualmente."""
        elapsed = 0
        interval = 2
        tag = f"[{module_name}]" if module_name else ""

        print(f"  {tag} 🔵 Modo MANUAL — resolvé el reCAPTCHA en el navegador")
        print(f"  {tag} ⏱️  Esperando hasta {max_wait}s...")

        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            try:
                response = await page.evaluate(
                    "() => document.getElementById('g-recaptcha-response')?.value || ''"
                )
                if response and len(response) > 20:
                    self.log(f"reCAPTCHA resuelto en {elapsed}s ✓")
                    return True
                if elapsed % 10 == 0:
                    print(f"  {tag} ⏳ Esperando... ({elapsed}s/{max_wait}s)")
            except Exception:
                pass

        self.warn(f"Timeout: reCAPTCHA no resuelto en {max_wait}s")
        return False

    async def detect_site_key(self, page: Page) -> str | None:
        """Extrae site key de reCAPTCHA de la página."""
        try:
            key = await page.evaluate(
                "() => document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey') || null"
            )
            if key:
                return key
            content = await page.content()
            match = re.search(r'"sitekey"\s*:\s*"([^"]+)"', content)
            if match:
                return match.group(1)
            match = re.search(r"data-sitekey=['\"]([^'\"]+)['\"]", content)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    async def inject_recaptcha_token(self, page: Page, token: str):
        """Inyecta token reCAPTCHA con sanitización."""
        token_safe = json.dumps(token)
        await page.evaluate(f"""
            document.getElementById('g-recaptcha-response').innerHTML = {token_safe};
            if (typeof ___grecaptcha_cfg !== 'undefined') {{
                Object.entries(___grecaptcha_cfg.clients).forEach(([k, v]) => {{
                    if (v.hasOwnProperty('callback')) {{
                        v.callback({token_safe});
                    }}
                }});
            }}
        """)
        self.log("✅ Token reCAPTCHA inyectado ✓")

    async def download_pdf(self, page: Page, selectors: list, output_path: Path, name: str = "PDF") -> Path | None:
        """Busca botón de descarga PDF y lo descarga."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for sel in selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    self.debug(f"Descargando con selector: {sel}")
                    try:
                        async with page.expect_download(timeout=30000) as dl_info:
                            await loc.first.click()
                        download = await dl_info.value
                        await download.save_as(output_path)
                        self.log(f"{name} descargado: {output_path} ✓")
                        self.open_pdf(output_path)
                        return output_path
                    except Exception as e:
                        self.debug(f"Error con selector {sel}: {e}")
                        continue
            except Exception:
                continue

        # Fallback: buscar cualquier link/botón visible con keywords
        try:
            all_links = await page.query_selector_all("a, button")
            for link in all_links:
                if await link.is_visible():
                    text = (await link.text_content() or "").lower()
                    href = await link.get_attribute("href") or ""
                    onclick = await link.get_attribute("onclick") or ""
                    keywords = ["imprimir", "pdf", "descargar", "generar"]
                    if any(k in text for k in keywords) or "pdf" in href.lower() or "imprimir" in onclick.lower():
                        try:
                            async with page.expect_download(timeout=30000) as dl_info:
                                await link.click()
                            download = await dl_info.value
                            await download.save_as(output_path)
                            self.log(f"{name} descargado: {output_path} ✓")
                            self.open_pdf(output_path)
                            return output_path
                        except Exception:
                            continue
        except Exception as e:
            self.debug(f"Error en fallback de descarga: {e}")

        self.warn(f"No se encontró botón de descarga para {name}")
        return None

    def open_pdf(self, pdf_path: Path):
        """Abre PDF con visor predeterminado."""
        try:
            sistema = platform.system()
            if sistema == "Windows":
                os.startfile(str(pdf_path))
            elif sistema == "Darwin":
                subprocess.run(["open", str(pdf_path)])
            else:
                subprocess.run(["xdg-open", str(pdf_path)])
            self.log("PDF abierto automáticamente")
        except Exception as e:
            self.warn(f"No se pudo abrir PDF: {e}")
            print(f"  Abrí manualmente: {pdf_path}")

    async def find_visible_inputs(self, page: Page, keyword: str = "") -> list:
        """Lista inputs visibles para debug. Si keyword, busca coincidencia."""
        inputs = await page.query_selector_all("input[type='text'], input:not([type])")
        found = []
        for inp in inputs:
            if await inp.is_visible():
                name = await inp.get_attribute("name") or ""
                id_attr = await inp.get_attribute("id") or ""
                placeholder = await inp.get_attribute("placeholder") or ""
                if not keyword or keyword.lower() in (name + id_attr + placeholder).lower():
                    found.append({"element": inp, "name": name, "id": id_attr, "placeholder": placeholder})
        return found

    async def debug_screenshot(self, page: Page, path: str = "debug.png"):
        """Toma screenshot para debug (solo si HEADLESS=false o VERBOSE)."""
        if not HEADLESS or os.getenv("VERBOSE", "false").lower() == "true":
            try:
                await page.screenshot(path=path)
                self.debug(f"Screenshot: {path}")
            except Exception:
                pass

    # ── Logging ───────────────────────────────────────────────────
    def log(self, msg: str):
        print(f"  [{self.name}] {msg}")

    def debug(self, msg: str):
        if os.getenv("VERBOSE", "false").lower() == "true":
            print(f"  [DEBUG][{self.name}] {msg}")

    def warn(self, msg: str):
        print(f"  [{self.name}] \u26a0 {msg}")

    def error(self, msg: str):
        print(f"  [{self.name}] \u274c {msg}")

    # ── HTML parsing helpers ─────────────────────────────────────
    def extract_curp_from_html(self, html: str) -> str | None:
        match = re.search(r"\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b", html)
        return match.group(1) if match else None

    def extract_nss_from_html(self, html: str) -> str | None:
        match = re.search(r"\b(\d{11})\b", html)
        return match.group(1) if match else None
