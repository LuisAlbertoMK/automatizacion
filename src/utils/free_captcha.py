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

import asyncio
import io
import os
import re
import tempfile
from pathlib import Path

from PIL import Image

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
    pass

try:
    import whisper  # noqa: F401
    WHISPER_AVAILABLE = True
except ImportError:
    pass

try:
    import requests  # noqa: F401
except ImportError:
    pass


from exceptions import FreeCaptchaError  # noqa: E402


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
        self._whisper_model = None
        self._init_verify()

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

            # Detectar si pide desafío (no siempre aparece)
            audio_btn = frame.locator("#recaptcha-audio-button")
            if await audio_btn.count() == 0:
                audio_btn = frame.locator("button[aria-label*='audio']")
            if await audio_btn.count() == 0:
                audio_btn = frame.locator("button[id='recaptcha-audio-button']")

            if await audio_btn.count() == 0:
                print("  [FreeCaptcha] Sin desafío de audio — verificando si ya resolvió...")
                # Puede que el checkbox haya sido suficiente
                token = await page.evaluate(
                    "() => document.getElementById('g-recaptcha-response')?.value || ''"
                )
                if token and len(token) > 20:
                    return token
                return "MANUAL"

            await audio_btn.first.click()
            await asyncio.sleep(3)

            # Obtener enlace del audio
            audio_link = await frame.locator("#audio-source").get_attribute("src")
            if not audio_link:
                print("  [FreeCaptcha] No se encontró enlace de audio")
                return "MANUAL"

            print("  [FreeCaptcha] Descargando audio...")
            resp = reqs.get(audio_link, timeout=30)
            audio_bytes = resp.content

            # Guardar temporalmente
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                audio_path = f.name

            try:
                # Cargar Whisper (una sola vez)
                if not self._whisper_model:
                    print("  [FreeCaptcha] Cargando Whisper (base)...")
                    import whisper
                    self._whisper_model = whisper.load_model("base")

                print("  [FreeCaptcha] Transcribiendo audio...")
                result = self._whisper_model.transcribe(audio_path, language="en")
                text = result["text"].strip()
                print(f"  [FreeCaptcha] Transcripción: '{text}'")

                # El audio challenge usa dígitos en inglés
                digits = re.sub(r"[^0-9]", "", text)
                if not digits:
                    print("  [FreeCaptcha] No se detectaron dígitos en el audio")
                    return "MANUAL"

                print(f"  [FreeCaptcha] Dígitos detectados: {digits}")

                # Ingresar respuesta
                await frame.locator("#audio-response").fill(digits)
                await asyncio.sleep(0.5)

                # Click verificar
                verify_btn = frame.locator("#recaptcha-verify-button")
                if await verify_btn.count() > 0:
                    await verify_btn.click()
                else:
                    # Fallback: submit alternativo
                    await page.keyboard.press("Enter")

                await asyncio.sleep(3)

                # Obtener token
                token = await page.evaluate(
                    "() => document.getElementById('g-recaptcha-response')?.value || ''"
                )

                if token and len(token) > 20:
                    print("  [FreeCaptcha] \u2705 reCAPTCHA resuelto con audio")
                    return token

                print("  [FreeCaptcha] Token no válido después del audio")
            finally:
                Path(audio_path).unlink(missing_ok=True)

        except Exception as e:
            print(f"  [FreeCaptcha] \u26a0 Error en audio challenge: {e}")

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
