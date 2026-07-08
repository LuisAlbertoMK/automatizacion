"""
modules/template.py — TEMPLATE para crear nuevos módulos de trámites.

Cómo usar:
  1. Copiá este archivo como modules/<tramite>.py
  2. Buscá "TODO" y reemplazá con los valores del portal
  3. Heredá de BaseModule para obtener browser lifecycle, selectores,
     captcha, logging, PDF, etc. GRATIS.
  4. Registrá el módulo en modules/orchestrator.py

Ejemplo:
    class RFCModule(BaseModule):
        async def consultar(self, rfc: str) -> dict:
            ...
"""

import time

from src.exceptions import ModuleError
from src.modules.base import BaseModule

# ── Config específica del trámite ──────────────────────────
# TODO: Cambiar URL, selectors y site_key
PORTAL_URL = "https://ejemplo.gob.mx/tramite"
SITE_KEY_FALLBACK = ""  # reCAPTCHA site key si aplica


class TramiteError(ModuleError):
    """Error específico de este trámite."""
    pass


class TramiteModule(BaseModule):
    """
    Módulo para [NOMBRE DEL TRÁMITE].
    Hereda de BaseModule: launch_browser, fill_field, click_first,
    resolve_image_captcha, detect_site_key, inject_recaptcha_token,
    wait_for_recaptcha, download_pdf, log/debug/warn/error.
    """

    def __init__(self, captcha_solver=None, use_ocr=True):
        # TODO: Cambiar "Tramite" por el nombre real
        super().__init__(
            captcha_solver=captcha_solver,
            use_ocr=use_ocr,
            name="Tramite"  # ← Cambiar
        )

    async def consultar(self, **kwargs) -> dict:
        """
        Punto de entrada principal.
        
        Args:
            kwargs: Datos necesarios para el trámite (curp, rfc, etc.)
            
        Returns:
            dict con resultados del trámite
        """
        # TODO: Validar parámetros requeridos
        # if not kwargs.get("curp"):
        #     raise TramiteError("Se requiere CURP")

        self.log("Iniciando consulta...")
        start = time.time()

        br = await self.launch_browser()
        page = br.page

        try:
            result = await self._run(page, **kwargs)
            elapsed = time.time() - start
            self.log(f"Completado en {elapsed:.1f}s")
            return result
        except TramiteError:
            raise
        except Exception as e:
            elapsed = time.time() - start
            self.error(f"Error en {elapsed:.1f}s: {e}")
            raise TramiteError(f"Error durante la consulta: {e}") from e
        finally:
            await self.close_browser(br)

    async def _run(self, page, **kwargs) -> dict:
        """Flujo principal del trámite."""
        # ── 1. Navegar al portal ──────────────────────────────
        await self.goto(page, PORTAL_URL)

        # ── 2. Llenar formulario ──────────────────────────────
        # TODO: Definir selectores y campos
        # ok = await self.fill_field(page, ["input[name='campo']"], kwargs.get("dato"))
        # if not ok:
        #     raise TramiteError("No se encontró el campo")

        # ── 3. Resolver CAPTCHA de imagen (si aplica) ────────
        # await self.resolve_image_captcha(
        #     page,
        #     img_selectors=["img[src*='captcha']"],
        #     input_selectors=["input[name='captcha']"],
        #     captcha_name="captcha"
        # )

        # ── 4. Resolver reCAPTCHA (si aplica) ────────────────
        # site_key = await self.detect_site_key(page)
        # if site_key:
        #     await self.wait_for_recaptcha(page, max_wait=120, module_name=self.name)

        # ── 5. Enviar formulario ──────────────────────────────
        # ok = await self.click_first(page, [
        #     "button[type='submit']",
        #     "button:has-text('Consultar')",
        # ], wait_nav=True)
        # if not ok:
        #     raise TramiteError("No se encontró botón de envío")

        # ── 6. Extraer resultado ──────────────────────────────
        # TODO: Parsear HTML o usar OCR
        # content = await page.content()
        # resultado = re.search(r"patron", content)

        return {
            "tramite": "TODO",
            "status": "implementar",
        }
