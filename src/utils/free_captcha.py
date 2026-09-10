"""
utils/free_captcha.py
Solución de CAPTCHAs 100% gratuita y local.

Reemplaza a 2captcha usando:
  - Tesseract OCR para CAPTCHAs de imagen numérica (CURP, Tenencia)
  - Whisper + audio challenge para reCAPTCHA v2 (IMSS, Antecedentes) — experimental

Modo de uso:
    solver = FreeCaptchaSolver()
    texto = solver.solve_image(image_bytes, numeric=True)
    token = await solver.solve_recaptcha_v2_audio(page, site_key, page_url)
"""

from __future__ import annotations

import asyncio
import io
import ipaddress
import logging
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

logger = logging.getLogger(__name__)

TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

TESSERACT_AVAILABLE = False
WHISPER_AVAILABLE = False
WGET_AVAILABLE = False

# ── Verificar disponibilidad de herramientas ────────────────────────────

try:
    import pytesseract
    for p in TESSERACT_PATHS:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except Exception:
    logger.debug("Tesseract no disponible")

try:
    import whisper  # noqa: F401
    WHISPER_AVAILABLE = True
except ImportError:
    pass

try:
    import requests  # noqa: F401
except ImportError:
    pass

# ── Whisper model singleton ────────────────────────────────────────
_whisper_model = None


def _get_whisper_model():
    """Lazy-load Whisper model once per process (~140MB)."""
    global _whisper_model
    if _whisper_model is None:
        import whisper as _whisper
        print("  [FreeCaptcha] Cargando Whisper (base)...")
        _whisper_model = _whisper.load_model("base")
    return _whisper_model


from src.exceptions import FreeCaptchaError  # noqa: E402

# ── M4 SSRF allowlist para audio challenge ───────────────────────────
_ALLOWED_AUDIO_HOSTS = {"www.google.com", "www.gstatic.com"}


def _is_allowed_audio_url(url: str) -> bool:
    """Valida que la URL de audio sea confiable (anti-SSRF).

    Exige scheme https, host en allowlist o subdominio
    .google.com/.gstatic.com, sin userinfo, sin IP literal,
    y puerto 443 o implícito. Retorna False ante cualquier
    excepción o URL vacía.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        # Rechaza userinfo (user:pass@host)
        if "@" in parsed.netloc:
            return False
        host = parsed.hostname
        if not host:
            return False
        host = host.lower()
        # Rechaza IPs literales v4/v6 (incluye IMDS, privadas, loopback)
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        if host not in _ALLOWED_AUDIO_HOSTS and not (
            host.endswith(".google.com") or host.endswith(".gstatic.com")
        ):
            return False
        # Solo puerto implícito o 443
        if parsed.port is not None and parsed.port != 443:
            return False
        return True
    except Exception:
        return False


class FreeCaptchaSolver:
    """
    Solver de CAPTCHAs gratuito y local.

    Interfaces compatibles con CaptchaSolver (utils/captcha.py):
      - solve_image(image_bytes, numeric=True)  -> str
      - solve_recaptcha_v2(site_key, page_url, auto=True) -> "MANUAL"

    Interfaz adicional asíncrona:
      - solve_recaptcha_v2_audio(page, site_key, page_url) -> token o "MANUAL"
    """

    def __init__(self, use_ocr: bool = True, use_whisper: bool = True):
        self.use_ocr = use_ocr and TESSERACT_AVAILABLE
        self.use_whisper = use_whisper and WHISPER_AVAILABLE
        self._init_verify()
        self._maybe_preload_whisper()

    def warmup(self):
        """Precarga explícita del modelo Whisper (opt-in, testeable).

        Llama a `_get_whisper_model()` solo si `self.use_whisper` es True.
        Si Whisper no está disponible o la carga falla, no-op silencioso
        (log debug, sin excepción). El singleton `_whisper_model` garantiza
        una sola carga por proceso.
        """
        if not self.use_whisper:
            logger.debug("Whisper warmup omitido: use_whisper=False")
            return None
        try:
            return _get_whisper_model()
        except Exception:
            logger.debug("Whisper warmup falló (no-op)", exc_info=True)
            return None

    def _maybe_preload_whisper(self):
        """Dispara precarga en background si WHISPER_PRELOAD=true (no bloqueante)."""
        try:
            if not self.use_whisper:
                return
            if os.getenv("WHISPER_PRELOAD", "").lower() != "true":
                return

            def _bg():
                try:
                    self.warmup()
                except Exception:
                    logger.debug("Whisper preload en background falló", exc_info=True)

            threading.Thread(target=_bg, daemon=True).start()
        except Exception:
            logger.debug("No se pudo lanzar preload de Whisper", exc_info=True)

    def _init_verify(self):
        if not TESSERACT_AVAILABLE:
            print("  [FreeCaptcha] \u26a0 OCR (Tesseract) no disponible")
            print("  [FreeCaptcha]   Instala: https://github.com/UB-Mannheim/tesseract/wiki")
        else:
            print("  [FreeCaptcha] \u2705 OCR (Tesseract) listo")

        if not WHISPER_AVAILABLE:
            print("  [FreeCaptcha] \u26a0 Whisper no disponible — audio challenge desactivado")
        else:
            print("  [FreeCaptcha] \u2705 Whisper disponible para audio challenge")

    # ────────────────────────────────────────────────────────────
    # Image CAPTCHA solver (CURP, Tenencia)
    # ────────────────────────────────────────────────────────────

    def solve_image(self, image_bytes: bytes, numeric: bool = True) -> str:
        """
        Resuelve CAPTCHA de imagen usando Tesseract OCR.

        Args:
            image_bytes: Bytes de la imagen del CAPTCHA
            numeric: True si solo contiene dígitos

        Returns:
            Texto del CAPTCHA resuelto
        """
        if not self.use_ocr:
            raise FreeCaptchaError(
                "OCR no disponible. Instala Tesseract desde: "
                "https://github.com/UB-Mannheim/tesseract/wiki"
            )

        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))

        # Intentar con preprocesamiento
        text = self._ocr_with_preprocess(img, numeric)

        # Si falla, intentar sin preprocesamiento
        if not text:
            raw = Image.open(io.BytesIO(image_bytes))
            config = "--psm 7"
            if numeric:
                config += " -c tessedit_char_whitelist=0123456789"
            text = pytesseract.image_to_string(raw, config=config).strip()
            text = re.sub(r"[^0-9]", "", text) if numeric else text.strip()

        if not text:
            raise FreeCaptchaError(
                "No se pudo resolver el CAPTCHA. "
                "Modo manual activado como respaldo."
            )

        print(f"  [FreeCaptcha] CAPTCHA resuelto: {text}")
        return text

    def _ocr_with_preprocess(self, img: Image.Image, numeric: bool) -> str:
        """Preprocesa la imagen y aplica OCR."""
        import pytesseract

        # Escala de grises
        if img.mode != "L":
            img = img.convert("L")

        # Escalar 3x para mejor precisión
        w, h = img.size
        img = img.resize((w * 3, h * 3), Image.LANCZOS)

        # Binarizar con threshold adaptativo
        img = img.point(lambda x: 0 if x < 140 else 255, "1")
        img = img.convert("L")

        config = "--psm 7"
        if numeric:
            config += " -c tessedit_char_whitelist=0123456789"

        text = pytesseract.image_to_string(img, config=config).strip()
        return re.sub(r"[^0-9]", "", text) if numeric else text.strip()

    # ────────────────────────────────────────────────────────────
    # reCAPTCHA v2 audio challenge solver (IMSS, Antecedentes)
    # ────────────────────────────────────────────────────────────

    @staticmethod
    async def _find_audio_button(frame):
        """Localiza el botón de audio del reCAPTCHA. Returns locator o None."""
        audio_btn = frame.locator("#recaptcha-audio-button")
        if await audio_btn.count() == 0:
            audio_btn = frame.locator("button[aria-label*='audio']")
        if await audio_btn.count() == 0:
            audio_btn = frame.locator("button[id='recaptcha-audio-button']")
        if await audio_btn.count() == 0:
            return None
        return audio_btn

    @staticmethod
    async def _check_existing_token(page):
        """Verifica si el checkbox fue suficiente para obtener token."""
        print("  [FreeCaptcha] Sin desafío de audio — verificando si ya resolvió...")
        token = await page.evaluate(
            "() => document.getElementById('g-recaptcha-response')?.value || ''"
        )
        if token and len(token) > 20:
            return token
        return "MANUAL"

    @staticmethod
    def _transcribir_y_extraer_digitos(audio_path):
        """Transcribe audio con Whisper y extrae dígitos. Returns str o None."""
        whisper_model = _get_whisper_model()
        print("  [FreeCaptcha] Transcribiendo audio...")
        result = whisper_model.transcribe(audio_path, language="en")
        text = result["text"].strip()
        print(f"  [FreeCaptcha] Transcripción: '{text}'")

        # El audio challenge usa dígitos en inglés
        digits = re.sub(r"[^0-9]", "", text)
        if not digits:
            print("  [FreeCaptcha] No se detectaron dígitos en el audio")
            return None
        print(f"  [FreeCaptcha] Dígitos detectados: {digits}")
        return digits

    @staticmethod
    async def _verificar_y_obtener_token(frame, page):
        """Hace click en verify (o Enter) y extrae el token. Returns token o None."""
        verify_btn = frame.locator("#recaptcha-verify-button")
        if await verify_btn.count() > 0:
            await verify_btn.click()
        else:
            # Fallback: submit alternativo
            await page.keyboard.press("Enter")

        await asyncio.sleep(3)

        token = await page.evaluate(
            "() => document.getElementById('g-recaptcha-response')?.value || ''"
        )

        if token and len(token) > 20:
            print("  [FreeCaptcha] ✅ reCAPTCHA resuelto con audio")
            return token

        print("  [FreeCaptcha] Token no válido después del audio")
        return None

    async def solve_recaptcha_v2_audio(
        self, page, site_key: str, page_url: str, max_wait: int = 120
    ) -> str:
        """
        Resuelve reCAPTCHA v2 usando el audio challenge + Whisper.

        Args:
            page: Página de Playwright donde está el reCAPTCHA
            site_key: Site key (no usado, se detecta dinámicamente)
            page_url: URL de la página
            max_wait: Tiempo máximo de espera

        Returns:
            Token g-recaptcha-response, o "MANUAL" si falla
        """
        if not self.use_whisper:
            print("  [FreeCaptcha] Whisper no disponible — modo manual")
            return "MANUAL"

        import requests as reqs

        try:
            frame = page.frame_locator("iframe[src*='recaptcha']")

            # Esperar y hacer clic en el checkbox
            await frame.locator(".recaptcha-checkbox-border").first.wait_for(
                timeout=10000
            )
            await asyncio.sleep(1)
            await frame.locator(".recaptcha-checkbox-border").first.click()
            await asyncio.sleep(2)

            # Buscar botón de audio
            audio_btn = await self._find_audio_button(frame)
            if audio_btn is None:
                return await self._check_existing_token(page)

            await audio_btn.first.click()
            await asyncio.sleep(3)

            # Obtener enlace del audio
            audio_link = await frame.locator("#audio-source").get_attribute("src")
            if not audio_link:
                print("  [FreeCaptcha] No se encontró enlace de audio")
                return "MANUAL"

            print("  [FreeCaptcha] Descargando audio...")
            if not _is_allowed_audio_url(audio_link):
                print(" [FreeCaptcha] URL de audio no confiable — abortando")
                return "MANUAL"
            resp = reqs.get(audio_link, timeout=30)
            audio_bytes = resp.content

            # Guardar temporalmente
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                audio_path = f.name

            try:
                digits = self._transcribir_y_extraer_digitos(audio_path)
                if not digits:
                    return "MANUAL"

                # Ingresar respuesta
                await frame.locator("#audio-response").fill(digits)
                await asyncio.sleep(0.5)

                token = await self._verificar_y_obtener_token(frame, page)
                if token:
                    return token
            finally:
                Path(audio_path).unlink(missing_ok=True)

        except Exception as e:
            print(f"  [FreeCaptcha] ⚠ Error en audio challenge: {e}")

        return "MANUAL"

    # ────────────────────────────────────────────────────────────
    # Interfaces compatibles con CaptchaSolver
    # ────────────────────────────────────────────────────────────

    def solve_recaptcha_v2(self, site_key: str, page_url: str, auto: bool = True) -> str:
        """
        Versión sincrónica. Siempre retorna "MANUAL" para que el módulo
        caiga en el flujo de resolución manual o use solve_recaptcha_v2_audio().
        """
        return "MANUAL"

    def solve_recaptcha_v3(
        self, site_key: str, page_url: str,
        action: str = "submit", min_score: float = 0.3, auto: bool = True
    ) -> str:
        """reCAPTCHA v3 no es soportado por el solver gratuito."""
        print("  [FreeCaptcha] \u26a0 reCAPTCHA v3 requiere 2captcha — modo manual")
        return "MANUAL"
