"""
modules/base.py
Clase base para todos los módulos de trámites.
Centraliza: selectors, captcha, PDF, logging, browser lifecycle.
"""
import asyncio
import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from playwright.async_api import Browser, Page, async_playwright
from playwright.async_api import TimeoutError as PwTimeout

from src.exceptions import ModuleError
from src.utils.browser_pool import BrowserPool


@dataclass
class BrowserResources:
    """Recursos de navegador — wrapping pool o directo.
    
    Evita el polimorfismo de tipo entre BrowserPool y Playwright
    que existía antes (H1 del análisis). El caller nunca necesita
    saber qué modo se usó.
    """
    browser: Browser
    page: Page
    _pool: Optional[BrowserPool] = None
    _playwright: Optional = None
    _context: Optional = None
    _from_pool: bool = field(default=False, init=False)

    def __post_init__(self):
        self._from_pool = self._pool is not None

    async def close(self):
        """Libera todos los recursos del navegador."""
        if self._context:
            try:
                await self._context.close()
            except Exception:
                self.debug("OCR no disponible")
            self._context = None

        if self._pool:
            try:
                await self._pool.release(self.browser)
            except Exception:
                self.debug("CaptchaSolver no disponible")
        else:
            try:
                await self.browser.close()
            except Exception:
                self.debug("Cliente IMAP no disponible")
            if self._playwright:
                try:
                    await self._playwright.__aexit__(None, None, None)
                except Exception:
                    self.debug("Whisper no disponible")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
TIMEOUT = int(os.getenv("TIMEOUT", "60")) * 1000
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "2.0"))
"""Segundos mínimos entre requests a portales (rate limiting)."""

_last_request_time = 0.0


async def _rate_limit():
    """Espera si es necesario para respetar REQUEST_DELAY entre requests."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < REQUEST_DELAY:
        await asyncio.sleep(REQUEST_DELAY - elapsed)
    _last_request_time = time.time()


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
                from src.utils.ocr import OCRExtractor
                self.ocr = OCRExtractor()
            except ImportError:
                pass
        self._selector_cache: dict[str, str] = {}
        # Inicializar logger estructurado
        try:
            from src.utils.logger import get_logger
            self._logger = get_logger(name)
        except Exception:
            self._logger = None

    async def launch_browser(self) -> BrowserResources:
        """Lanza browser con configuración anti-detección.

        Usa Firefox con fingerprint real para evitar WAF/Cloudflare.
        El User-Agent de Chrome sobre Firefox es detectado como bot.
        
        Intenta usar el browser pool para reutilizar instancias (sin overhead de 3-5s).
        Si el pool no está disponible, lanza un browser nuevo (fallback).
        
        Devuelve un BrowserResources que encapsula pool/directo — el caller
        nunca necesita saber qué modo se usó.
        """
        pool = None
        try:
            from src.utils.browser_pool import get_browser_pool
            pool = get_browser_pool()
            browser = await pool.acquire()
        except Exception:
            pool = None

        if pool is not None:
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
                    "Gecko/20100101 Firefox/131.0"
                ),
                locale="es-MX",
                timezone_id="America/Mexico_City",
                permissions=["geolocation"],
            )
            await context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
            page = await context.new_page()
            return BrowserResources(browser, page, _pool=pool, _context=context)

        # ── Fallback: sin pool ──────────────────────────────────
        _extra_args = []
        if os.getenv("PLAYWRIGHT_NO_SANDBOX", "").lower() == "true":
            _extra_args = ["--no-sandbox"]

        p = await async_playwright().__aenter__()
        browser = await p.firefox.launch(
            headless=HEADLESS,
            args=_extra_args,
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            # Firefox con UA real de Firefox — Chrome UA en Firefox delata al bot
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) "
                "Gecko/20100101 Firefox/131.0"
            ),
            locale="es-MX",
            timezone_id="America/Mexico_City",
            permissions=["geolocation"],
        )
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await context.new_page()
        return BrowserResources(browser, page, _playwright=p, _context=context)

    async def close_browser(self, br: BrowserResources):
        """Cierra browser y playwright, o libera browser al pool."""
        await br.close()

    async def goto(self, page: Page, url: str, fallback_url: str = None):
        """Navega a URL con fallback y rate limiting.

        Usa domcontentloaded + wait fijo en vez de networkidle porque
        los portales del gobierno suelen tener analytics/tracking que
        impiden que networkidle se dispare.
        """
        await _rate_limit()
        last_error = None
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT)
            await page.wait_for_timeout(2000)
            return
        except Exception as e:
            last_error = e
            if fallback_url:
                try:
                    await page.goto(fallback_url, wait_until="domcontentloaded", timeout=TIMEOUT)
                    await page.wait_for_timeout(2000)
                    return
                except Exception as e2:
                    last_error = e2
        raise ModuleError(
            f"No se pudo navegar a {url} (fallback: {fallback_url}): {last_error}"
        ) from last_error

    async def fill_field(self, page: Page, selectors: list, value: str) -> bool:
        """Llena un campo probando múltiples selectores. Retorna True si encontró alguno."""
        cache_key = str(tuple(selectors))

        if cache_key in self._selector_cache:
            cached_sel = self._selector_cache[cache_key]
            try:
                loc = page.locator(cached_sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    self.debug(f"Llenando campo con selector cacheado: {cached_sel}")
                    await loc.first.fill(value)
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                self.debug("Selector cacheado fallo, probando resto")

        for sel in selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    self.debug(f"Llenando campo con selector: {sel}")
                    await loc.first.fill(value)
                    await asyncio.sleep(0.3)
                    self._selector_cache[cache_key] = sel
                    return True
            except Exception as e:
                self.debug(f"fill_field: selector {sel} falló: {e}")
                continue
        return False

    async def click_first(self, page: Page, selectors: list, wait_nav: bool = False, timeout_nav: int = 30000) -> bool:
        """Hace clic en el primer selector visible. Retorna True si encontró."""
        cache_key = str(tuple(selectors))

        if cache_key in self._selector_cache:
            cached_sel = self._selector_cache[cache_key]
            try:
                loc = page.locator(cached_sel)
                if await loc.count() > 0 and await loc.first.is_visible():
                    self.debug(f"Haciendo clic con selector cacheado: {cached_sel}")
                    if wait_nav:
                        async with page.expect_navigation(timeout=timeout_nav):
                            await loc.first.click()
                        await asyncio.sleep(1)
                    else:
                        await loc.first.click()
                        await asyncio.sleep(1)
                    return True
            except Exception:
                self.debug("Cached click selector fallo")

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
                    self._selector_cache[cache_key] = sel
                    return True
            except PwTimeout:
                self.debug(f"Navigation timeout en {sel}, continuando...")
                return True
            except Exception as e:
                self.debug(f"click_first: selector {sel} falló: {e}")
                continue
        return False

    def clear_selector_cache(self):
        """Limpia el caché de selectores exitosos."""
        self._selector_cache.clear()

    async def resolve_image_captcha(self, page: Page, img_selectors: list, input_selectors: list,
                                     numeric: bool = True, captcha_name: str = "captcha") -> bool:
        """Detecta y resuelve CAPTCHA de imagen. Retorna True si lo resolvió."""
        captcha_img = None
        for sel in img_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                captcha_img = loc.first
                break

        if not captcha_img:
            self.log("Sin CAPTCHA de imagen detectado")
            return False

        self.log("CAPTCHA de imagen detectado, descargando...")

        # Obtener src de la imagen
        src = await captcha_img.get_attribute("src")
        if not src:
            return False

        if src.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(page.url)
            src = f"{parsed.scheme}://{parsed.netloc}{src}"

        try:
            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None, lambda: requests.get(src, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
            )
            resp.raise_for_status()
            img_bytes = resp.content
        except Exception as e:
            self.warn(f"Error descargando CAPTCHA: {e}")
            return False

        solution = None
        if self.solver:
            try:
                loop = asyncio.get_running_loop()
                solution = await loop.run_in_executor(
                    None, self.solver.solve_image, img_bytes, numeric
                )
                self.log(f"CAPTCHA resuelto: {solution}")
            except Exception as e:
                self.warn(f"Solver falló: {e}")

        if not solution and os.getenv("DEBUG", "false").lower() == "true":
            solution = os.getenv("CAPTCHA_VALUE", "").strip()
            if solution:
                self.log("CAPTCHA desde variable de entorno (DEBUG mode)")

        if not solution:
            self.warn("Sin solución de CAPTCHA")
            return False

        return await self.fill_field(page, input_selectors, solution)

    async def wait_for_recaptcha(self, page: Page, max_wait: int = 120, module_name: str = ""):
        """Espera a que el usuario resuelva reCAPTCHA manualmente."""
        elapsed = 0
        interval = 2
        tag = f"[{module_name}]" if module_name else ""

        self.log(f"{tag} Modo MANUAL — resolvé el reCAPTCHA en el navegador")
        self.log(f"{tag} [..] Esperando hasta {max_wait}s...")

        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            try:
                response = await page.evaluate(
                    "() => document.getElementById('g-recaptcha-response')?.value || ''"
                )
                if response and len(response) > 20:
                    self.log(f"reCAPTCHA resuelto en {elapsed}s [OK]")
                    return True
                if elapsed % 10 == 0:
                    self.log(f"{tag} [..] Esperando... ({elapsed}s/{max_wait}s)")
            except Exception as e:
                self.debug(f"Error checking reCAPTCHA: {e}")

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
        except Exception as e:
            self.debug(f"Error detectando site key: {e}")
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
        self.log("[OK] Token reCAPTCHA inyectado [OK]")

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
                        self.log(f"{name} descargado: {output_path} [OK]")
                        self.open_pdf(output_path)
                        return output_path
                    except Exception as e:
                        self.debug(f"download_pdf: error con selector {sel}: {e}")
                        continue
            except Exception as e:
                self.debug(f"download_pdf: locator error en {sel}: {e}")
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
                            self.log(f"{name} descargado: {output_path} [OK]")
                            self.open_pdf(output_path)
                            return output_path
                        except Exception as e:
                            self.debug(f"download_pdf: fallback click falló: {e}")
                            continue
        except Exception as e:
            self.debug(f"Error en fallback de descarga: {e}")

        self.warn(f"No se encontró botón de descarga para {name}")
        return None

    def open_pdf(self, pdf_path: Path):
        """Abre PDF con visor predeterminado (solo si no es headless)."""
        if HEADLESS:
            self.debug(f"Headless mode — omitiendo open_pdf: {pdf_path}")
            return
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
            self.log(f"Abrí manualmente: {pdf_path}")

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
                logger.debug("Error cerrando browser en close_all")

    # ── Logging estructurado ─────────────────────────────────────
    def log(self, msg: str):
        """Info genérica."""
        if hasattr(self, '_logger') and self._logger:
            self._logger.info(msg)
        else:
            print(f"  [{self.name}] {msg}")

    def debug(self, msg: str):
        """Debug (solo si VERBOSE)."""
        if hasattr(self, '_logger') and self._logger:
            self._logger.debug(msg)
        elif os.getenv("VERBOSE", "false").lower() == "true":
            print(f"  [DEBUG][{self.name}] {msg}")

    def warn(self, msg: str):
        """Advertencia."""
        if hasattr(self, '_logger') and self._logger:
            self._logger.warn(msg)
        else:
            print(f"  [{self.name}] \u26a0 {msg}")

    def error(self, msg: str):
        """Error."""
        if hasattr(self, '_logger') and self._logger:
            self._logger.error(msg)
        else:
            print(f"  [{self.name}] \u274c {msg}")

    # ── HTML parsing helpers ─────────────────────────────────────
    def extract_curp_from_html(self, html: str) -> str | None:
        match = re.search(r"\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b", html)
        return match.group(1) if match else None

    def extract_nss_from_html(self, html: str) -> str | None:
        match = re.search(r"\b(\d{11})\b", html)
        return match.group(1) if match else None
