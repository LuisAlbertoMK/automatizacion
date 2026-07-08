"""
utils/rate_limiter.py
Rate limiter por dominio — evita bloqueos por requests muy seguidos.
Usa asyncio.sleep() entre requests al mismo dominio.

Uso:
    from src.utils.rate_limiter import limiter
    await limiter.wait("serviciosdigitales.imss.gob.mx")
    await page.goto(url, ...)
"""
import asyncio
import time
from collections import defaultdict
from typing import Optional


class RateLimiter:
    """Rate limiter por dominio con retardo configurable."""

    def __init__(self, default_delay: float = 1.5):
        self._last: dict[str, float] = defaultdict(float)
        self._delay: dict[str, float] = {}
        self._default = default_delay

    def set_delay(self, domain: str, delay: float) -> None:
        """Configura retardo específico para un dominio."""
        self._delay[domain] = delay

    async def wait(self, domain: str) -> None:
        """Espera el tiempo necesario desde el último request al dominio."""
        delay = self._delay.get(domain, self._default)
        elapsed = time.monotonic() - self._last[domain]
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last[domain] = time.monotonic()

    def reset(self, domain: Optional[str] = None) -> None:
        """Resetea el timer para un dominio (o todos si none)."""
        if domain:
            self._last.pop(domain, None)
        else:
            self._last.clear()


limiter = RateLimiter()
