"""
utils/captcha.py
Cliente para resolver CAPTCHAs vía 2captcha.com

Soporta:
  - ImageCaptcha  (imágenes numéricas simples — usado por gob.mx/curp)
  - reCAPTCHA v2  (usado por IMSS, OADPRS, INE, SRE)
  - reCAPTCHA v3  (usado por INE, SAT)
"""

import os
import time
import base64
import requests
from pathlib import Path


BASE_URL = "https://2captcha.com"


class CaptchaError(Exception):
    pass


class CaptchaSolver:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("CAPTCHA_API_KEY", "")
        if not self.api_key:
            raise CaptchaError(
                "No se encontró CAPTCHA_API_KEY. "
                "Configúrala en config.env o como variable de entorno."
            )
        self._verify_balance()

    def _verify_balance(self):
        """Verifica que haya saldo suficiente en 2captcha."""
        try:
            r = requests.get(
                f"{BASE_URL}/res.php",
                params={"key": self.api_key, "action": "getbalance"},
                timeout=10,
            )
            balance = float(r.text)
            if balance < 0.001:
                raise CaptchaError(
                    f"Saldo insuficiente en 2captcha: ${balance:.4f} USD. "
                    "Recarga en https://2captcha.com"
                )
            print(f"  [captcha] Saldo 2captcha: ${balance:.4f} USD ✓")
        except (ValueError, requests.RequestException):
            # No bloqueamos si falla la verificación de saldo
            pass

    # ────────────────────────────────────────────────────────────
    # ImageCaptcha (imagen con texto/números — gob.mx/curp)
    # ────────────────────────────────────────────────────────────
    def solve_image(self, image_bytes: bytes, numeric: bool = True) -> str:
        """
        Resuelve un CAPTCHA de imagen (base64).
        numeric=True indica que solo contiene dígitos.
        Costo aprox: $0.001–0.002 USD
        """
        b64 = base64.b64encode(image_bytes).decode()

        params = {
            "key": self.api_key,
            "method": "base64",
            "body": b64,
            "json": 1,
        }
        if numeric:
            params["numeric"] = 1

        r = requests.post(f"{BASE_URL}/in.php", data=params, timeout=30)
        data = r.json()

        if data.get("status") != 1:
            raise CaptchaError(f"Error enviando imagen: {data.get('request')}")

        task_id = data["request"]
        return self._wait_for_result(task_id)

    # ────────────────────────────────────────────────────────────
    # reCAPTCHA v2 (IMSS, OADPRS, INE, SRE)
    # ────────────────────────────────────────────────────────────
    def solve_recaptcha_v2(self, site_key: str, page_url: str, auto: bool = True) -> str:
        """
        Resuelve reCAPTCHA v2.
        
        Args:
            site_key: Site key del reCAPTCHA
            page_url: URL de la página
            auto: Si True, usa 2captcha. Si False, modo semiautomático (espera manual)
        
        Returns:
            Token g-recaptcha-response
        
        Costo aprox: $0.002 USD. Tiempo: 15–45 seg.
        """
        if not auto:
            # Modo semiautomático - no envía a 2captcha
            print("  [captcha] ⚠ Modo SEMIAUTOMÁTICO activado")
            print("  [captcha] Resuelve el reCAPTCHA manualmente en el navegador")
            return "MANUAL"  # Señal para que el módulo espere
        
        params = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
            "json": 1,
        }
        r = requests.post(f"{BASE_URL}/in.php", data=params, timeout=30)
        data = r.json()

        if data.get("status") != 1:
            raise CaptchaError(f"Error enviando reCAPTCHA v2: {data.get('request')}")

        task_id = data["request"]
        print("  [captcha] Resolviendo reCAPTCHA v2 automáticamente (15–45 seg)...")
        return self._wait_for_result(task_id, max_wait=120)

    # ────────────────────────────────────────────────────────────
    # reCAPTCHA v3 (INE, SAT)
    # ────────────────────────────────────────────────────────────
    def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "submit", min_score: float = 0.3, auto: bool = True
    ) -> str:
        """
        Resuelve reCAPTCHA v3.
        
        Args:
            site_key: Site key del reCAPTCHA
            page_url: URL de la página
            action: Acción del reCAPTCHA
            min_score: Score mínimo requerido
            auto: Si True, usa 2captcha. Si False, modo semiautomático
        
        Returns:
            Token reCAPTCHA
        
        Costo aprox: $0.004 USD. Tiempo: 10–30 seg.
        """
        if not auto:
            print("  [captcha] ⚠ Modo SEMIAUTOMÁTICO activado")
            print("  [captcha] reCAPTCHA v3 se resolverá automáticamente por el navegador")
            return "MANUAL"
        
        params = {
            "key": self.api_key,
            "method": "userrecaptcha",
            "version": "v3",
            "googlekey": site_key,
            "pageurl": page_url,
            "action": action,
            "min_score": min_score,
            "json": 1,
        }
        r = requests.post(f"{BASE_URL}/in.php", data=params, timeout=30)
        data = r.json()

        if data.get("status") != 1:
            raise CaptchaError(f"Error enviando reCAPTCHA v3: {data.get('request')}")

        task_id = data["request"]
        print("  [captcha] Resolviendo reCAPTCHA v3 automáticamente (10–30 seg)...")
        return self._wait_for_result(task_id, max_wait=90)

    # ────────────────────────────────────────────────────────────
    # Espera resultado
    # ────────────────────────────────────────────────────────────
    def _wait_for_result(self, task_id: str, max_wait: int = 120) -> str:
        """Polling hasta que 2captcha devuelva la solución."""
        elapsed = 0
        interval = 5

        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval

            r = requests.get(
                f"{BASE_URL}/res.php",
                params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                timeout=15,
            )
            data = r.json()

            if data.get("status") == 1:
                print(f"  [captcha] Resuelto en {elapsed}s ✓")
                return data["request"]

            if data.get("request") not in ("CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"):
                raise CaptchaError(f"Error 2captcha: {data.get('request')}")

        raise CaptchaError(f"Timeout: CAPTCHA no resuelto en {max_wait}s")
