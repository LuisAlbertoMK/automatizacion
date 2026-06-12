"""
modules/nss.py
Automatiza la consulta del Número de Seguridad Social (NSS) en IMSS.
Portal: https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS

Flujo:
  1. Abrir portal IMSS
  2. Ingresar CURP y correo electrónico
  3. Resolver reCAPTCHA v2
  4. Enviar solicitud
  5. Esperar correo del IMSS con el NSS (automático vía IMAP)
  6. Extraer y retornar NSS

Tiempo estimado: 30–60 segundos (depende del correo del IMSS)
"""

import os
import re
import time
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Page, TimeoutError as PwTimeout

try:
    from utils.ocr import OCRExtractor
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from captcha_solver_imss import IMSCaptchaSolver, CaptchaStore
    IMSS_SOLVER_AVAILABLE = True
except ImportError:
    IMSS_SOLVER_AVAILABLE = False


OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output"))
TIMEOUT    = int(os.getenv("TIMEOUT", "60")) * 1000
HEADLESS   = os.getenv("HEADLESS", "true").lower() == "true"

PORTAL_URL = (
    "https://serviciosdigitales.imss.gob.mx/"
    "gestionAsegurados-web-externo/asignacionNSS"
)

# Site key de reCAPTCHA del portal IMSS (puede cambiar — se detecta dinámicamente)
RECAPTCHA_SITE_KEY_FALLBACK = "6LfFGgkTAAAAAMDDVFwSuYPKqI9Kc_qp9c2qXxlz"


class NSSError(Exception):
    pass


class NSSModule:
    def __init__(self, captcha_solver=None, mail_reader=None, use_ocr=True):
        self.solver      = captcha_solver
        self.mail_reader = mail_reader
        self.use_ocr     = use_ocr and OCR_AVAILABLE
        self.ocr         = OCRExtractor() if self.use_ocr else None
        
        if use_ocr and not OCR_AVAILABLE:
            print("  [NSS] [!] OCR no disponible. Instala: pip install pytesseract pillow")

    async def consultar(self, curp: str, correo: str) -> dict:
        """
        Consulta el NSS del IMSS para una CURP dada.

        Args:
            curp:   CURP de 18 caracteres
            correo: Correo electrónico para recibir el NSS

        Returns:
            dict con: nss, curp, correo, pdf_path
        """
        if not curp or not correo:
            raise NSSError("Se requieren CURP y correo electrónico")

        curp = curp.upper().strip()
        print(f"\n  [NSS] Iniciando consulta para CURP {curp[:4]}****")
        start = time.time()

        async with async_playwright() as pw:
            browser = await pw.firefox.launch(
                headless=HEADLESS,
            )
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

            try:
                result = await self._run(page, curp=curp, correo=correo)
                elapsed = time.time() - start
                print(f"  [NSS] [OK] Completado en {elapsed:.1f}s")
                return result
            except NSSError:
                raise
            except Exception as e:
                elapsed = time.time() - start
                print(f"  [NSS] [!] Error en {elapsed:.1f}s: {e}")
                raise NSSError(f"Error durante la consulta: {e}")
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass  # Ignorar errores al cerrar (puede que ya esté cerrado)

    async def _run(self, page: Page, curp: str, correo: str) -> dict:
        """Flujo principal."""

        # ── 1. Abrir portal ────────────────────────────────────────
        print("  [NSS] Abriendo portal IMSS...")
        try:
            await page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
        except PwTimeout:
            # El portal IMSS a veces tarda en cargar
            await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
        
        await asyncio.sleep(2)
        
        # Tomar screenshot para debug
        try:
            await page.screenshot(path="debug_nss_portal.png")
            print("  [DEBUG] Screenshot guardado: debug_nss_portal.png")
        except Exception:
            pass

        # ── 2. Verificar que el formulario esté disponible ─────────
        await self._esperar_formulario(page)

        # ── 3. Ingresar CURP ───────────────────────────────────────
        await self._ingresar_curp(page, curp)

        # ── 4. Ingresar correo ─────────────────────────────────────
        await self._ingresar_correo(page, correo)

        # ── 5. Confirmar correo ─────────────────────────────────────
        await self._ingresar_confirmacion_correo(page, correo)

        # ── 6. Resolver CAPTCHA de imagen ──────────────────────────
        await self._resolver_captcha_imagen(page)

        # ── 7. Resolver reCAPTCHA v2 ───────────────────────────────
        await self._resolver_recaptcha(page)

        # ── 8. Enviar formulario ───────────────────────────────────
        await self._enviar_formulario(page)

        # ── 9. Obtener NSS ─────────────────────────────────────────
        nss = await self._obtener_nss(page, correo)

        return {
            "nss":    nss,
            "curp":   curp,
            "correo": correo,
        }

    async def _esperar_formulario(self, page: Page):
        """Espera que el formulario principal esté listo."""
        form_selectors = [
            "form", "input[name='curp']", "input[id='curp']",
            ".formulario", "#formNSS",
        ]
        for sel in form_selectors:
            try:
                await page.wait_for_selector(sel, timeout=15000)
                print("  [NSS] Formulario listo [OK]")
                return
            except PwTimeout:
                continue

        # Si no encontramos formulario, puede ser que el portal esté caído
        content = await page.content()
        if "mantenimiento" in content.lower() or "no disponible" in content.lower():
            raise NSSError("El portal IMSS está en mantenimiento. Intenta más tarde.")

        print("  [NSS] Continuando sin confirmar formulario...")

    async def _ingresar_curp(self, page: Page, curp: str):
        """Ingresa la CURP en el formulario."""
        print(f"  [NSS] Ingresando CURP: {curp[:4]}****")
        
        # Listar todos los inputs para debug
        all_inputs = await page.query_selector_all("input")
        print(f"  [DEBUG] Total de inputs encontrados: {len(all_inputs)}")
        
        curp_selectors = [
            "input[name='curp']",
            "input[id='curp']",
            "input[name='txtCurp']",
            "input[id='txtCurp']",
            "input[placeholder*='CURP']",
            "input[placeholder*='curp']",
            "input[maxlength='18']",
            "input[type='text'][maxlength='18']",
            "#curpInput",
            ".curp-field",
        ]
        
        for sel in curp_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Llenando CURP con selector: {sel}")
                        await loc.first.fill(curp)
                        await asyncio.sleep(0.3)
                        print(f"  [NSS] CURP ingresada [OK]")
                        return
            except Exception as e:
                print(f"  [DEBUG] Error con selector {sel}: {e}")
                continue
        
        # Enfoque alternativo
        print("  [DEBUG] Intentando enfoque alternativo para CURP...")
        try:
            all_text_inputs = await page.query_selector_all("input[type='text'], input:not([type])")
            for inp in all_text_inputs:
                is_visible = await inp.is_visible()
                if is_visible:
                    name = await inp.get_attribute("name") or ""
                    id_attr = await inp.get_attribute("id") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    print(f"  [DEBUG] Input visible: name={name}, id={id_attr}, placeholder={placeholder}")
                    
                    if "curp" in name.lower() or "curp" in id_attr.lower() or "curp" in placeholder.lower():
                        await inp.fill(curp)
                        print(f"  [NSS] CURP ingresada en campo detectado [OK]")
                        return
        except Exception as e:
            print(f"  [DEBUG] Error en enfoque alternativo: {e}")
        
        raise NSSError("No se encontró el campo CURP en el portal IMSS. Verifica que el portal esté accesible.")

    async def _ingresar_correo(self, page: Page, correo: str):
        """Ingresa el correo electrónico y su confirmación."""
        print(f"  [NSS] Ingresando correo: {correo}")
        
        email_selectors = [
            "input[type='email']",
            "input[name='correo']",
            "input[name='email']",
            "input[id='correo']",
            "input[id='email']",
            "input[placeholder*='correo']",
            "input[placeholder*='email']",
            "input[placeholder*='Correo']",
            "input[placeholder*='Email']",
        ]
        
        for sel in email_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Llenando correo con selector: {sel}")
                        await loc.first.fill(correo)
                        await asyncio.sleep(0.3)
                        print(f"  [NSS] Correo ingresado [OK]")
                        return
            except Exception as e:
                print(f"  [DEBUG] Error con selector {sel}: {e}")
                continue
        
        # Enfoque alternativo
        print("  [DEBUG] Intentando enfoque alternativo para correo...")
        try:
            all_inputs = await page.query_selector_all("input")
            for inp in all_inputs:
                is_visible = await inp.is_visible()
                if is_visible:
                    inp_type = await inp.get_attribute("type") or ""
                    name = await inp.get_attribute("name") or ""
                    id_attr = await inp.get_attribute("id") or ""
                    placeholder = await inp.get_attribute("placeholder") or ""
                    
                    if inp_type == "email" or "correo" in name.lower() or "email" in name.lower() or \
                       "correo" in id_attr.lower() or "email" in id_attr.lower() or \
                       "correo" in placeholder.lower() or "email" in placeholder.lower():
                        await inp.fill(correo)
                        print(f"  [NSS] Correo ingresado en campo detectado [OK]")
                        return
        except Exception as e:
            print(f"  [DEBUG] Error en enfoque alternativo: {e}")
        
        raise NSSError("No se encontró el campo de correo en el portal IMSS. Verifica que el portal esté accesible.")

    async def _ingresar_confirmacion_correo(self, page: Page, correo: str):
        """Ingresa la confirmación del correo electrónico (correoElectronicoFiscal)."""
        confirm_selectors = [
            "input[name='correoElectronicoFiscal.correo']",
            "input[id='correoConfirmacionInput']",
            "input[placeholder*='Confirma']",
        ]
        for sel in confirm_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Llenando confirmación correo con: {sel}")
                        await loc.first.fill(correo)
                        await asyncio.sleep(0.3)
                        print(f"  [NSS] Confirmación de correo ingresada [OK]")
                        return
            except Exception:
                continue
        print("  [NSS] Sin campo de confirmación de correo, continuando...")

    async def _resolver_captcha_imagen(self, page: Page):
        """
        Detecta y resuelve el CAPTCHA de imagen del IMSS.

        Pipeline:
          1. Descarga la imagen del CaptchaServlet
          2. Guarda copia local + abre para inspección visual
          3. Resuelve con IMSCaptchaSolver (EasyOCR + Tesseract ensemble)
          4. Fallback a CAPTCHA_VALUE (manual) si el solver no confía
          5. Fallback a FreeCaptchaSolver (legacy)
        """
        import requests as reqs
        from pathlib import Path

        captcha_img = await page.query_selector(
            "img[src*='Captcha'], img[src*='captcha'], "
            "img[src*='CaptchaServlet'], img[src*='captchaServlet']"
        )
        captcha_input = await page.query_selector("input[name='captcha']")

        if not captcha_img or not captcha_input:
            print("  [NSS] Sin CAPTCHA de imagen detectado, continuando...")
            return

        src = await captcha_img.get_attribute("src") or ""
        if not src:
            print("  [NSS] CAPTCHA de imagen sin src, continuando...")
            return

        if src.startswith("/"):
            src = f"https://serviciosdigitales.imss.gob.mx{src}"

        print(f"  [NSS] CAPTCHA de imagen detectado, descargando...")
        try:
            resp = reqs.get(src, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            img_bytes = resp.content
            print(f"  [NSS] Imagen descargada: {len(img_bytes)} bytes")
        except Exception as e:
            print(f"  [NSS] [!] Error descargando CAPTCHA: {e}")
            return

        # ── Guardar imagen para debug visual ─────────────────────
        captcha_path = Path("debug_captcha_imss.png")
        captcha_path.write_bytes(img_bytes)
        import subprocess
        try:
            subprocess.Popen(["start", str(captcha_path.absolute())], shell=True)
        except Exception:
            pass

        # ── 1. Pipeline IMSCaptchaSolver (EasyOCR + Tesseract) ──
        valor = ""
        from captcha_solver_imss import IMSCaptchaSolver, CaptchaStore
        ims_solver = IMSCaptchaSolver(verbose=True)
        ims_result = ims_solver.solve(img_bytes)

        if ims_result["success"] and ims_result["score"] >= 0.5:
            valor = ims_result["value"]
            print(f"  [NSS] CAPTCHA resuelto por ensemble "
                  f"(engine: {ims_result['engine']}, "
                  f"score: {ims_result['score']:.2f}): '{valor}'")
        else:
            print(f"  [NSS] Ensemble no confiable "
                  f"(score: {ims_result.get('score', 0):.2f})")

        # ── 2. Fallback: FreeCaptchaSolver (legacy) ──────────────
        if not valor:
            ocr_hint = ""
            if self.solver and hasattr(self.solver, "solve_image"):
                try:
                    ocr_hint = self.solver.solve_image(img_bytes, numeric=False)
                    print(f"  [FreeCaptcha] OCR sugiere: '{ocr_hint}'")
                except Exception:
                    pass
            if ocr_hint:
                valor = ocr_hint

        # ── 3. Fallback: variable de entorno (manual) ────────────
        if not valor:
            valor = os.getenv("CAPTCHA_VALUE", "").strip()
            if valor:
                print(f"  [NSS] CAPTCHA desde variable de entorno: '{valor}'")

        if not valor:
            print("  [NSS] [!] Sin CAPTCHA, continuando...")
            return

        await captcha_input.fill(valor)
        await asyncio.sleep(0.3)
        print(f"  [NSS] CAPTCHA ingresado: {valor} [OK]")

    async def _resolver_recaptcha(self, page: Page):
        """Detecta y resuelve el reCAPTCHA v2 del portal IMSS (modo semiautomático)."""
        await asyncio.sleep(1)

        # Detectar site key dinámicamente
        site_key = await self._detectar_site_key(page)
        if not site_key:
            print("  [NSS] Sin reCAPTCHA detectado, continuando...")
            return

        print(f"  [NSS] reCAPTCHA detectado (key: {site_key[:20]}...)")

        # ── 1. Intentar audio challenge (FreeCaptchaSolver) ──
        audio_method = getattr(self.solver, 'solve_recaptcha_v2_audio', None) if self.solver else None
        if audio_method:
            print("  [NSS] Intentando audio challenge (Whisper)...")
            token = await audio_method(page, site_key, PORTAL_URL)
            if token and token != "MANUAL":
                await self._inyectar_token_recaptcha(page, token)
                return
            print("  [NSS] Audio no disponible, usando modo alternativo...")

        # ── 2. Modo automático (2captcha) o manual ──
        if self.solver:
            auto_mode = os.getenv("RECAPTCHA_AUTO", "false").lower() == "true"
            
            if auto_mode:
                print("  [NSS] Modo AUTOMÁTICO - Resolviendo CAPTCHA...")
                token = self.solver.solve_recaptcha_v2(site_key, PORTAL_URL, auto=True)
                
                if token and token != "MANUAL":
                    await self._inyectar_token_recaptcha(page, token)
                else:
                    print("  [NSS] [!] Solver no disponible en auto, modo manual...")
                    await self._esperar_recaptcha_resuelto(page, max_wait=120)
            else:
                # Modo SEMIAUTOMÁTICO (por defecto)
                print("  [NSS] 🔵 Modo MANUAL activado")
                print("  [NSS] 👉 Resuelve el reCAPTCHA en el navegador")
                print("  [NSS] [..]️  Esperando hasta 120 segundos...")
                await self._esperar_recaptcha_resuelto(page, max_wait=120)
        else:
            # Sin solver configurado - modo manual
            print("  [NSS] 🔵 Modo MANUAL - Sin solver configurado")
            print("  [NSS] 👉 Resuelve el reCAPTCHA en el navegador")
            print("  [NSS] [..]️  Esperando hasta 120 segundos...")
            await self._esperar_recaptcha_resuelto(page, max_wait=120)

    async def _inyectar_token_recaptcha(self, page: Page, token: str):
        """Inyecta un token de reCAPTCHA en la página con sanitización."""
        # Sanitizar token para evitar inyección en page.evaluate()
        import json
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
        print("  [NSS] [OK] Token reCAPTCHA inyectado [OK]")
    
    async def _esperar_recaptcha_resuelto(self, page: Page, max_wait: int = 120):
        """Espera a que el usuario resuelva el reCAPTCHA manualmente."""
        elapsed = 0
        interval = 2
        
        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            
            # Verificar si el reCAPTCHA fue resuelto
            try:
                response = await page.evaluate("""
                    () => {
                        const resp = document.getElementById('g-recaptcha-response');
                        return resp ? resp.value : '';
                    }
                """)
                
                if response and len(response) > 20:
                    print(f"  [NSS] [OK] reCAPTCHA resuelto en {elapsed}s")
                    return
                
                if elapsed % 10 == 0:
                    print(f"  [NSS] [..] Esperando... ({elapsed}s/{max_wait}s)")
            except Exception:
                pass
        
        print(f"  [NSS] [!] Timeout: reCAPTCHA no resuelto en {max_wait}s")
        print(f"  [NSS] Continuando de todas formas...")

    async def _detectar_site_key(self, page: Page) -> str | None:
        """Extrae el site key de reCAPTCHA de la página."""
        try:
            # Buscar en atributos data-sitekey
            key = await page.evaluate("""
                () => {
                    const el = document.querySelector('[data-sitekey]');
                    return el ? el.getAttribute('data-sitekey') : null;
                }
            """)
            if key:
                return key

            # Buscar en el contenido HTML
            content = await page.content()
            match = re.search(r'"sitekey"\s*:\s*"([^"]+)"', content)
            if match:
                return match.group(1)
            match = re.search(r"data-sitekey=['\"]([^'\"]+)['\"]", content)
            if match:
                return match.group(1)

        except Exception:
            pass

        # ¿Hay iframe de reCAPTCHA? Usamos el fallback conocido
        try:
            frames = page.frames
            for frame in frames:
                if "recaptcha" in frame.url:
                    return RECAPTCHA_SITE_KEY_FALLBACK
        except Exception:
            pass

        return None

    async def _enviar_formulario(self, page: Page):
        """Hace clic en el botón de envío y espera la navegación post-submit."""
        print("  [NSS] Buscando botón de envío...")
        
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Enviar')",
            "button:has-text('Consultar')",
            "button:has-text('Aceptar')",
            "button:has-text('Solicitar')",
            "button:has-text('Continuar')",
            "#btnEnviar",
            "#btnSubmit",
            "#btnConsultar",
            ".btn-submit",
            ".btn-primary",
        ]
        
        for sel in submit_selectors:
            try:
                loc = page.locator(sel)
                if await loc.count() > 0:
                    is_visible = await loc.first.is_visible()
                    if is_visible:
                        print(f"  [DEBUG] Haciendo clic en botón: {sel}")
                        # Usar expect_navigation para esperar la redirección post-submit
                        async with page.expect_navigation(timeout=30000):
                            await loc.first.click()
                        print("  [NSS] Formulario enviado [OK]")
                        await asyncio.sleep(2)
                        # Tomar screenshot de la página de resultado
                        try:
                            await page.screenshot(path="nss_resultado.png")
                            print("  [DEBUG] Screenshot post-submit: nss_resultado.png")
                        except Exception:
                            pass
                        return
            except PwTimeout:
                # Timeout en navigation - la página no navegó, pero quizás el submit funcionó
                print("  [NSS] Submit realizado (sin redirección visible)")
                await asyncio.sleep(2)
                return
            except Exception as e:
                print(f"  [DEBUG] Error con selector {sel}: {e}")
                continue
        
        raise NSSError("No se encontró el botón de envío. Verifica que el formulario esté completo.")

    async def _obtener_nss(self, page: Page, correo: str) -> str:
        """
        Intenta obtener el NSS de la respuesta de la página usando HTML y OCR.
        Si no está en página, espera el correo del IMSS.
        """

        # Primero: buscar NSS directo en la respuesta de la página (HTML)
        await asyncio.sleep(2)
        try:
            content = await page.content()
        except Exception as e:
            print(f"  [NSS] [!] Error al leer página post-submit: {e}")
            print(f"  [NSS] Intentando con URL actual...")
            try:
                url = page.url
                print(f"  [NSS] URL actual: {url}")
                # Puede que la página haya redirigido, intentar reload
                await page.wait_for_load_state("networkidle", timeout=15000)
                content = await page.content()
            except Exception as e2:
                print(f"  [NSS] [!] Error recuperando página: {e2}")
                raise NSSError(
                    "La conexión con el portal se perdió después del envío. "
                    "Posiblemente el portal rechazó el CAPTCHA o la sesión expiró."
                )

        # NSS = 11 dígitos consecutivos
        nss_candidates = re.findall(r"\b(\d{11})\b", content)
        if nss_candidates:
            nss = nss_candidates[0]
            print(f"  [NSS] NSS encontrado en página (HTML): {nss} [OK]")
            return nss
        
        # Segundo: intentar con OCR si está disponible
        if self.use_ocr:
            print("  [NSS] Usando OCR para buscar NSS en la página...")
            try:
                screenshot_path = "resultado_nss_temp.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                
                ocr_data = self.ocr.extract_from_screenshot(screenshot_path)
                
                if ocr_data["nss"]:
                    nss = ocr_data["nss"]
                    print(f"  [NSS] NSS encontrado con OCR: {nss} [OK]")
                    
                    try:
                        os.remove(screenshot_path)
                    except:
                        pass
                    
                    return nss
                
                try:
                    os.remove(screenshot_path)
                except:
                    pass
            except Exception as e:
                print(f"  [NSS] Error al usar OCR: {e}")

        # Tercero: verificar error de CAPTCHA
        captcha_error_texts = [
            "captcha no válido", "captcha inválido", "captcha incorrecto",
            "código captcha", "código de verificación",
        ]
        if any(t in content.lower() for t in captcha_error_texts):
            error_msg = re.search(
                r"(el\s+)?captcha\s+(no\s+)?(válido|inválido|incorrecto|erróne)",
                content, re.IGNORECASE
            )
            msg = error_msg.group(0) if error_msg else "CAPTCHA inválido"
            print(f"  [NSS] [!] Error detectado en respuesta: '{msg}'")
            raise NSSError(
                f"CAPTCHA inválido. El portal rechazó el código ingresado. "
                f"Intentá de nuevo verificando bien los caracteres."
            )

        # Cuarto: verificar si hay mensaje de éxito
        success_texts = [
            "se ha enviado", "revisa tu correo", "correo enviado",
            "número de seguridad social", "tu nss",
        ]
        if any(t in content.lower() for t in success_texts):
            print("  [NSS] Solicitud enviada. Esperando correo del IMSS...")

            if self.mail_reader:
                mail_data = self.mail_reader.wait_for_imss_email(max_wait_sec=180)
                if mail_data.get("nss"):
                    print(f"  [NSS] NSS extraído del correo: {mail_data['nss']} [OK]")
                    return mail_data["nss"]
                else:
                    link = mail_data.get("verification_link", "")
                    if link:
                        print(f"  [NSS] Link de verificación recibido: {link}")
                        await page.goto(link, timeout=TIMEOUT)
                        await asyncio.sleep(3)
                        try:
                            content2 = await page.content()
                            nss2 = re.findall(r"\b(\d{11})\b", content2)
                            if nss2:
                                print(f"  [NSS] NSS encontrado tras verificar correo: {nss2[0]} [OK]")
                                return nss2[0]
                        except Exception:
                            pass
            else:
                print(
                    f"  [NSS] [!] Revisa manualmente el correo {correo}\n"
                    f"  El IMSS enviará el NSS en unos minutos."
                )
                return "ENVIADO_AL_CORREO"

        # Quinto: revisar si hay algún número de 11 dígitos visible en la página
        # (el NSS puede no tener word boundary si está en una tabla)
        all_nums = re.findall(r"\d{11}", content)
        if all_nums:
            print(f"  [NSS] Posible NSS encontrado (sin boundary): {all_nums[0]} [OK]")
            return all_nums[0]

        raise NSSError(
            "No se pudo obtener el NSS. "
            "Verifica que la CURP sea correcta y el portal esté disponible."
        )
