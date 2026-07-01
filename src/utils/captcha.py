"""
utils/captcha.py
Cliente para resolver CAPTCHAs v+¡a 2captcha.com

Soporta:
  - ImageCaptcha  (im+ígenes num+®ricas simples ÔÇö usado por gob.mx/curp)
  - reCAPTCHA v2  (usado por IMSS, OADPRS, INE, SRE)
  - reCAPTCHA v3  (usado por INE, SAT)
"""

import asyncio
import base64
import os
import time

import requests

from exceptions import CaptchaError

BASE_URL = "https://2captcha.com"


class CaptchaSolver:
    _balance_cache: float | None = None
    _balance_ts: float = 0
    _balance_ttl: float = 60.0

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("CAPTCHA_API_KEY", "")
        if not self.api_key:
            raise CaptchaError(
                "No se encontro CAPTCHA_API_KEY. "
                "Configurala en config.env o como variable de entorno."
            )
        self._verify_balance()

    def _verify_balance(self):
        """Verifica saldo en 2captcha con cache de 60s."""
        now = time.monotonic()
        if now - self._balance_ts < self._balance_ttl and self._balance_cache is not None:
            return
        try:
            r = requests.get(
                f"{BASE_URL}/res.php",
                params={"key": self.api_key, "action": "getbalance"},
                timeout=10,
            )
            self._balance_cache = float(r.text)
            self._balance_ts = now
            if self._balance_cache < 0.001:
                raise CaptchaError(
                    f"Saldo insuficiente en 2captcha: ${self._balance_cache:.4f} USD. "
                    "Recarga en https://2captcha.com"
                )
            print(f"  [captcha] Saldo 2captcha: ${self._balance_cache:.4f} USD [OK]")
        except (ValueError, requests.RequestException):
            pass

    # ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    # ImageCaptcha (imagen con texto/n+¦meros ÔÇö gob.mx/curp)
    # ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    def solve_image(self, image_bytes: bytes, numeric: bool = True) -> str:
        """
        Resuelve un CAPTCHA de imagen (base64).
        numeric=True indica que solo contiene d+¡gitos.
        Costo aprox: $0.001ÔÇô0.002 USD
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

    # -----------------------------------------------------------------------------
    # reCAPTCHA v2 (IMSS, OADPRS, INE, SRE)
    # -----------------------------------------------------------------------------
    def solve_recaptcha_v2(self, site_key: str, page_url: str, auto: bool = True) -> str:
        """
        Resuelve reCAPTCHA v2.
        
        Args:
            site_key: Site key del reCAPTCHA
            page_url: URL de la p+ígina
            auto: Si True, usa 2captcha. Si False, modo semiautom+ítico (espera manual)
        
        Returns:
            Token g-recaptcha-response
        
        Costo aprox: $0.002 USD. Tiempo: 15ÔÇô45 seg.
        """
        if not auto:
            # Modo semiautom+ítico - no env+¡a a 2captcha
            print("  [captcha] [!] Modo SEMIAUTOM+üTICO activado")
            print("  [captcha] Resuelve el reCAPTCHA manualmente en el navegador")
            return "MANUAL"  # Se+¦al para que el m+¦dulo espere

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
        print("  [captcha] Resolviendo reCAPTCHA v2 automáticamente (1545 seg)...")
        return self._wait_for_result(task_id, max_wait=120)

    # -----------------------------------------------------------------------------
    # reCAPTCHA v3 (INE, SAT)
    # -----------------------------------------------------------------------------
    def solve_recaptcha_v3(
        self, site_key: str, page_url: str, action: str = "submit", min_score: float = 0.3, auto: bool = True
    ) -> str:
        """
        Resuelve reCAPTCHA v3.
        
        Args:
            site_key: Site key del reCAPTCHA
            page_url: URL de la p+ígina
            action: Acci+¦n del reCAPTCHA
            min_score: Score m+¡nimo requerido
            auto: Si True, usa 2captcha. Si False, modo semiautom+ítico
        
        Returns:
            Token reCAPTCHA
        
        Costo aprox: $0.004 USD. Tiempo: 10ÔÇô30 seg.
        """
        if not auto:
            print("  [captcha] [!] Modo SEMIAUTOM+üTICO activado")
            print("  [captcha] reCAPTCHA v3 se resolver+í autom+íticamente por el navegador")
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
        print("  [captcha] Resolviendo reCAPTCHA v3 autom+íticamente (10ÔÇô30 seg)...")
        return self._wait_for_result(task_id, max_wait=90)

    # ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    # Versiones async (no bloquean el event loop)
    # ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    async def solve_image_async(self, image_bytes: bytes, numeric: bool = True) -> str:
        """Async: Resuelve un CAPTCHA de imagen sin bloquear."""
        b64 = base64.b64encode(image_bytes).decode()
        params = {"key": self.api_key, "method": "base64", "body": b64, "json": 1}
        if numeric:
            params["numeric"] = 1

        r = await asyncio.to_thread(
            requests.post, f"{BASE_URL}/in.php", data=params, timeout=30
        )
        data = r.json()
        if data.get("status") != 1:
            raise CaptchaError(f"Error enviando imagen: {data.get('request')}")
        return await self._wait_for_result_async(data["request"])

    async def solve_recaptcha_v2_async(self, site_key: str, page_url: str, auto: bool = True) -> str:
        """Async: Resuelve reCAPTCHA v2 sin bloquear."""
        if not auto:
            print("  [captcha] [!] Modo SEMIAUTOM+üTICO activado")
            return "MANUAL"
        params = {
            "key": self.api_key, "method": "userrecaptcha",
            "googlekey": site_key, "pageurl": page_url, "json": 1,
        }
        r = await asyncio.to_thread(requests.post, f"{BASE_URL}/in.php", data=params, timeout=30)
        data = r.json()
        if data.get("status") != 1:
            raise CaptchaError(f"Error enviando reCAPTCHA v2: {data.get('request')}")
        print("  [captcha] Resolviendo reCAPTCHA v2 async (15ÔÇô45 seg)...")
        return await self._wait_for_result_async(data["request"], max_wait=120)

    async def solve_recaptcha_v3_async(
        self, site_key: str, page_url: str, action: str = "submit",
        min_score: float = 0.3, auto: bool = True,
    ) -> str:
        """Async: Resuelve reCAPTCHA v3 sin bloquear."""
        if not auto:
            print("  [captcha] [!] Modo SEMIAUTOM+üTICO activado")
            return "MANUAL"
        params = {
            "key": self.api_key, "method": "userrecaptcha", "version": "v3",
            "googlekey": site_key, "pageurl": page_url, "action": action,
            "min_score": min_score, "json": 1,
        }
        r = await asyncio.to_thread(requests.post, f"{BASE_URL}/in.php", data=params, timeout=30)
        data = r.json()
        if data.get("status") != 1:
            raise CaptchaError(f"Error enviando reCAPTCHA v3: {data.get('request')}")
        print("  [captcha] Resolviendo reCAPTCHA v3 async (10ÔÇô30 seg)...")
        return await self._wait_for_result_async(data["request"], max_wait=90)

    async def _wait_for_result_async(self, task_id: str, max_wait: int = 120) -> str:
        """Async polling hasta que 2captcha devuelva la soluci+¦n.

        Incluye retry con exponential backoff ante errores transitorios
        (Pilar 5 ÔÇö Fiabilidad & Resiliencia).
        """
        elapsed = 0
        interval = 2
        retries = 0
        max_retries = 3
        base_delay = 2

        while elapsed < max_wait:
            await asyncio.sleep(interval)
            elapsed += interval
            # Adaptive polling: faster early, slower later
            if elapsed > 60:
                interval = 10
            elif elapsed > 20:
                interval = 5

            try:
                r = await asyncio.to_thread(
                    requests.get, f"{BASE_URL}/res.php",
                    params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                    timeout=15,
                )
            except requests.RequestException as e:
                retries += 1
                if retries > max_retries:
                    raise CaptchaError(f"Error de red tras {max_retries} reintentos: {e}")
                delay = base_delay ** retries
                print(f"  [captcha] [!] Error de red, reintento {retries}/{max_retries} en {delay}s...")
                await asyncio.sleep(delay)
                continue

            data = r.json()
            if data.get("status") == 1:
                print(f"  [captcha] Resuelto en {elapsed}s [OK]")
                return data["request"]
            if data.get("request") not in ("CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"):
                raise CaptchaError(f"Error 2captcha: {data.get('request')}")

        raise CaptchaError(f"Timeout: CAPTCHA no resuelto en {max_wait}s")

    # ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
    def _wait_for_result(self, task_id: str, max_wait: int = 120) -> str:
        """Polling hasta que 2captcha devuelva la soluci+¦n.

        Incluye retry con exponential backoff ante errores transitorios
        (Pilar 5 ÔÇö Fiabilidad & Resiliencia).
        """
        elapsed = 0
        interval = 5
        retries = 0
        max_retries = 3
        base_delay = 2

        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval

            try:
                r = requests.get(
                    f"{BASE_URL}/res.php",
                    params={"key": self.api_key, "action": "get", "id": task_id, "json": 1},
                    timeout=15,
                )
            except requests.RequestException as e:
                retries += 1
                if retries > max_retries:
                    raise CaptchaError(f"Error de red tras {max_retries} reintentos: {e}")
                delay = base_delay ** retries
                print(f"  [captcha] [!] Error de red, reintento {retries}/{max_retries} en {delay}s...")
                time.sleep(delay)
                continue

            data = r.json()

            if data.get("status") == 1:
                print(f"  [captcha] Resuelto en {elapsed}s [OK]")
                return data["request"]

            if data.get("request") not in ("CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"):
                raise CaptchaError(f"Error 2captcha: {data.get('request')}")

        raise CaptchaError(f"Timeout: CAPTCHA no resuelto en {max_wait}s")
