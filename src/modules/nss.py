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

import asyncio
import os
import re
import time
from pathlib import Path

import requests
from playwright.async_api import TimeoutError as PwTimeout

from exceptions import NSSError
from modules.base import TIMEOUT, BaseModule

try:
    from utils.ocr import OCRExtractor  # noqa: F401
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from captcha_solver_imss import CaptchaStore, IMSCaptchaSolver  # noqa: F401
    IMSS_SOLVER_AVAILABLE = True
except ImportError:
    IMSS_SOLVER_AVAILABLE = False


PORTAL_URL = (
    "https://serviciosdigitales.imss.gob.mx/"
    "gestionAsegurados-web-externo/asignacionNSS"
)

# Site key de reCAPTCHA del portal IMSS (fallback si no se detecta dinámicamente)
RECAPTCHA_SITE_KEY_FALLBACK = "6LfFGgkTAAAAAMDDVFwSuYPKqI9Kc_qp9c2qXxlz"


class NSSModule(BaseModule):
    """
    Módulo de consulta NSS IMSS.
    Hereda de BaseModule para browser lifecycle, fill_field, click_first,
    detect_site_key, inject_recaptcha_token y wait_for_recaptcha.
    """

    def __init__(self, captcha_solver=None, mail_reader=None, use_ocr=True):
        super().__init__(captcha_solver=captcha_solver, use_ocr=use_ocr, name="NSS")
        self.mail_reader = mail_reader

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
        self.log(f"Iniciando consulta para CURP {curp[:4]}****")
        start = time.time()

        p, browser, page = await self.launch_browser()

        try:
            result = await self._run(page, curp=curp, correo=correo)
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return result
        except NSSError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise NSSError(f"Error durante la consulta: {e}") from e
        finally:
            await self.close_browser(p, browser)

    async def _run(self, page, curp: str, correo: str) -> dict:
        """Flujo principal del trámite NSS."""
        # ── 1. Abrir portal ────────────────────────────────────────
        self.log("Abriendo portal IMSS...")
        await self.goto(page, PORTAL_URL)

        await self.debug_screenshot(page, "debug_nss_portal.png")

        # ── 2. Verificar formulario ────────────────────────────────
        await self._esperar_formulario(page)

        # ── 3-5. Ingresar datos ────────────────────────────────────
        await self._ingresar_curp(page, curp)
        await self._ingresar_correo(page, correo)
        await self._ingresar_confirmacion_correo(page, correo)

        # ── 6. Resolver CAPTCHA de imagen ──────────────────────────
        await self._resolver_captcha_imagen(page)

        # ── 7. Resolver reCAPTCHA v2 ───────────────────────────────
        await self._resolver_recaptcha(page)

        # ── 8. Enviar formulario ───────────────────────────────────
        await self._enviar_formulario(page)

        # ── 9. Obtener NSS ─────────────────────────────────────────
        nss = await self._obtener_nss(page, correo)

        return {"nss": nss, "curp": curp, "correo": correo}

    # ── Métodos específicos NSS (no heredados) ─────────────────────────

    async def _esperar_formulario(self, page):
        """Espera que el formulario principal esté listo."""
        form_selectors = [
            "form", "input[name='curp']", "input[id='curp']",
            ".formulario", "#formNSS",
        ]
        for sel in form_selectors:
            try:
                await page.wait_for_selector(sel, timeout=15000)
                self.log("Formulario listo")
                return
            except PwTimeout:
                continue

        # Si no encontramos formulario, puede ser que el portal esté caído
        content = await page.content()
        if "mantenimiento" in content.lower() or "no disponible" in content.lower():
            raise NSSError("El portal IMSS está en mantenimiento. Intenta más tarde.")

        self.debug("Continuando sin confirmar formulario...")

    async def _ingresar_curp(self, page, curp: str):
        """Ingresa la CURP en el formulario usando BaseModule.fill_field."""
        self.log(f"Ingresando CURP: {curp[:4]}****")
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
        ok = await self.fill_field(page, curp_selectors, curp)
        if ok:
            self.log("CURP ingresada")
            return

        # Enfoque alternativo: buscar cualquier input visible
        self.debug("Intentando enfoque alternativo para CURP...")
        inputs = await self.find_visible_inputs(page, keyword="curp")
        if inputs:
            await inputs[0]["element"].fill(curp)
            self.log("CURP ingresada en campo detectado")
            return

        raise NSSError("No se encontró el campo CURP en el portal IMSS. Verifica que el portal esté accesible.")

    async def _ingresar_correo(self, page, correo: str):
        """Ingresa el correo electrónico usando BaseModule.fill_field."""
        self.log(f"Ingresando correo: {correo}")
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
        ok = await self.fill_field(page, email_selectors, correo)
        if ok:
            self.log("Correo ingresado")
            return

        # Enfoque alternativo
        self.debug("Intentando enfoque alternativo para correo...")
        inputs = await self.find_visible_inputs(page, keyword="correo")
        if not inputs:
            inputs = await self.find_visible_inputs(page, keyword="email")
        if inputs:
            await inputs[0]["element"].fill(correo)
            self.log("Correo ingresado en campo detectado")
            return

        raise NSSError("No se encontró el campo de correo en el portal IMSS. Verifica que el portal esté accesible.")

    async def _ingresar_confirmacion_correo(self, page, correo: str):
        """Ingresa la confirmación del correo."""
        confirm_selectors = [
            "input[name='correoElectronicoFiscal.correo']",
            "input[id='correoConfirmacionInput']",
            "input[placeholder*='Confirma']",
        ]
        ok = await self.fill_field(page, confirm_selectors, correo)
        if ok:
            self.log("Confirmación de correo ingresada")
        else:
            self.debug("Sin campo de confirmación de correo, continuando...")

    async def _resolver_captcha_imagen(self, page):
        """
        Detecta y resuelve el CAPTCHA de imagen del IMSS.

        Pipeline:
          1. Descarga la imagen del CaptchaServlet
          2. Resuelve con IMSCaptchaSolver (CNN + EasyOCR + Tesseract ensemble)
          3. Fallback a FreeCaptchaSolver
          4. Fallback a CAPTCHA_VALUE (manual)
        """
        captcha_img = await page.query_selector(
            "img[src*='Captcha'], img[src*='captcha'], "
            "img[src*='CaptchaServlet'], img[src*='captchaServlet']"
        )
        captcha_input = await page.query_selector("input[name='captcha']")

        if not captcha_img or not captcha_input:
            self.debug("Sin CAPTCHA de imagen detectado, continuando...")
            return

        src = await captcha_img.get_attribute("src") or ""
        if not src:
            self.debug("CAPTCHA de imagen sin src, continuando...")
            return

        if src.startswith("/"):
            src = f"https://serviciosdigitales.imss.gob.mx{src}"

        self.log("CAPTCHA de imagen detectado, descargando...")
        try:
            resp = requests.get(src, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            resp.raise_for_status()
            img_bytes = resp.content
            self.debug(f"Imagen descargada: {len(img_bytes)} bytes")
        except Exception as e:
            self.warn(f"Error descargando CAPTCHA: {e}")
            return

        # ── 1. Pipeline IMSCaptchaSolver ──
        valor = ""
        if IMSS_SOLVER_AVAILABLE:
            try:
                from captcha_solver_imss import IMSCaptchaSolver
                ims_solver = IMSCaptchaSolver(verbose=False)
                loop = asyncio.get_running_loop()
                ims_result = await loop.run_in_executor(
                    None, ims_solver.solve, img_bytes
                )
            except Exception as e:
                self.warn(f"IMSCaptchaSolver falló: {e}")
                ims_result = {"success": False, "score": 0}
        else:
            self.debug("IMSCaptchaSolver no disponible, saltando...")
            ims_result = {"success": False, "score": 0}

        if ims_result["success"] and ims_result["score"] >= 0.5:
            valor = ims_result["value"]
            self.log(f"CAPTCHA resuelto por ensemble "
                     f"(engine: {ims_result['engine']}, "
                     f"score: {ims_result['score']:.2f}): '{valor}'")
        else:
            self.warn(f"Ensemble no confiable "
                      f"(score: {ims_result.get('score', 0):.2f})")

        # ── 2. Fallback: FreeCaptchaSolver ──
        if not valor and self.solver and hasattr(self.solver, "solve_image"):
            try:
                ocr_hint = self.solver.solve_image(img_bytes, numeric=False)
                if ocr_hint:
                    valor = ocr_hint
                    self.debug(f"FreeCaptcha sugiere: '{valor}'")
            except Exception:
                pass

        # ── 3. Fallback: variable de entorno (manual) ──
        if not valor:
            valor = os.getenv("CAPTCHA_VALUE", "").strip()
            if valor:
                self.debug(f"CAPTCHA desde variable de entorno: '{valor}'")

        if not valor:
            self.warn("Sin CAPTCHA, continuando...")
            return

        await captcha_input.fill(valor)
        await asyncio.sleep(0.3)
        self.log(f"CAPTCHA ingresado: {valor}")

    async def _resolver_recaptcha(self, page):
        """Detecta y resuelve el reCAPTCHA v2 del portal IMSS."""
        await asyncio.sleep(1)

        # Detectar site key dinámicamente (BaseModule.detect_site_key)
        site_key = await self.detect_site_key(page)
        if not site_key:
            self.debug("Sin reCAPTCHA detectado, continuando...")
            return

        self.debug(f"reCAPTCHA detectado (key: {site_key[:20]}...)")

        # ── 1. Intentar audio challenge ──
        audio_method = getattr(self.solver, 'solve_recaptcha_v2_audio', None) if self.solver else None
        if audio_method:
            self.log("Intentando audio challenge (Whisper)...")
            token = await audio_method(page, site_key, PORTAL_URL)
            if token and token != "MANUAL":
                await self.inject_recaptcha_token(page, token)
                return

        # ── 2. Modo automático (2captcha) o manual ──
        if self.solver:
            auto_mode = os.getenv("RECAPTCHA_AUTO", "false").lower() == "true"

            if auto_mode:
                self.log("Modo AUTOMÁTICO - Resolviendo CAPTCHA...")
                loop = asyncio.get_running_loop()
                token = await loop.run_in_executor(
                    None, self.solver.solve_recaptcha_v2, site_key, PORTAL_URL, True
                )
                if token and token != "MANUAL":
                    await self.inject_recaptcha_token(page, token)
                else:
                    self.warn("Solver no disponible en auto, modo manual...")
                    await self.wait_for_recaptcha(page, max_wait=120, module_name="NSS")
            else:
                self.log("Modo MANUAL — resolvé el reCAPTCHA en el navegador")
                await self.wait_for_recaptcha(page, max_wait=120, module_name="NSS")
        else:
            self.log("Modo MANUAL — Sin solver configurado")
            await self.wait_for_recaptcha(page, max_wait=120, module_name="NSS")

    async def _enviar_formulario(self, page):
        """Hace clic en el botón de envío y espera la navegación post-submit."""
        self.log("Buscando botón de envío...")

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

        ok = await self.click_first(page, submit_selectors, wait_nav=True, timeout_nav=30000)
        if ok:
            self.log("Formulario enviado")
            await self.debug_screenshot(page, "nss_resultado.png")
        else:
            raise NSSError("No se encontró el botón de envío. Verifica que el formulario esté completo.")

    async def _obtener_nss(self, page, correo: str) -> str:
        """
        Intenta obtener el NSS de la respuesta de la página usando HTML y OCR.
        Si no está en página, espera el correo del IMSS.
        """
        await asyncio.sleep(2)
        try:
            content = await page.content()
        except Exception as e:
            self.error(f"Error al leer página post-submit: {e}")
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
                content = await page.content()
            except Exception as e2:
                self.error(f"Error recuperando página: {e2}")
                raise NSSError(
                    "La conexión con el portal se perdió después del envío. "
                    "Posiblemente el portal rechazó el CAPTCHA o la sesión expiró."
                ) from e2

        # NSS = 11 dígitos consecutivos
        nss_candidates = re.findall(r"\b(\d{11})\b", content)
        if nss_candidates:
            nss = nss_candidates[0]
            self.log(f"NSS encontrado en página: {nss}")
            return nss

        # Segundo: intentar con OCR
        if self.use_ocr:
            self.log("Usando OCR para buscar NSS en la página...")
            try:
                screenshot_path = "resultado_nss_temp.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                ocr_data = self.ocr.extract_from_screenshot(screenshot_path)
                if ocr_data.get("nss"):
                    nss = ocr_data["nss"]
                    self.log(f"NSS encontrado con OCR: {nss}")
                    Path(screenshot_path).unlink(missing_ok=True)
                    return nss
                Path(screenshot_path).unlink(missing_ok=True)
            except Exception as e:
                self.warn(f"Error al usar OCR: {e}")

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
            self.error(f"Error detectado en respuesta: '{msg}'")
            raise NSSError(
                "CAPTCHA inválido. El portal rechazó el código ingresado. "
                "Intentá de nuevo verificando bien los caracteres."
            )

        # Cuarto: verificar mensaje de éxito
        success_texts = [
            "se ha enviado", "revisa tu correo", "correo enviado",
            "número de seguridad social", "tu nss",
        ]
        if any(t in content.lower() for t in success_texts):
            self.log("Solicitud enviada. Esperando correo del IMSS...")

            if self.mail_reader:
                mail_data = self.mail_reader.wait_for_imss_email(max_wait_sec=180)
                if mail_data.get("nss"):
                    self.log(f"NSS extraído del correo: {mail_data['nss']}")
                    return mail_data["nss"]
                link = mail_data.get("verification_link", "")
                if link:
                    self.debug(f"Link de verificación recibido: {link}")
                    await page.goto(link, timeout=TIMEOUT)
                    await asyncio.sleep(3)
                    try:
                        content2 = await page.content()
                        nss2 = re.findall(r"\b(\d{11})\b", content2)
                        if nss2:
                            self.log(f"NSS encontrado tras verificar correo: {nss2[0]}")
                            return nss2[0]
                    except Exception:
                        pass
            else:
                self.warn(f"Revisá manualmente el correo {correo}")
                return "ENVIADO_AL_CORREO"

        # Quinto: buscar cualquier número de 11 dígitos
        all_nums = re.findall(r"\d{11}", content)
        if all_nums:
            self.log(f"Posible NSS encontrado: {all_nums[0]}")
            return all_nums[0]

        raise NSSError(
            "No se pudo obtener el NSS. "
            "Verifica que la CURP sea correcta y el portal esté disponible."
        )
