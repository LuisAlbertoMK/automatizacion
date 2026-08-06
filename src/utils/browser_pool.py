"""
utils/browser_pool.py
Pool de browsers Firefox para reutilizar instancias y eliminar overhead de 3-5s por trámite.
"""
import asyncio
import logging
import time
from typing import Optional

from playwright.async_api import Browser, Playwright, async_playwright

logger = logging.getLogger(__name__)


class BrowserPool:
    """
    Pool de browsers Firefox pre-lanzados.
    
    Características:
    - Pre-lanza N browsers al inicializar
    - Reutiliza browsers entre trámites (acquire/release)
    - Timeout de inactividad: lazy check en acquire() (sin background drain)
    - Singleton pattern para compartir entre módulos
    """
    
    def __init__(self, pool_size: int = 2, idle_timeout: int = 300,
                 max_uses: int = 10):
        """
        Args:
            pool_size: Número de browsers a pre-lanzar (default: 2)
            idle_timeout: Segundos antes de cerrar browser inactivo (default: 300)
            max_uses: Máximo número de usos antes de reciclar browser (default: 10).
                Previene memory leak de cookies/cache/sesiones (200MB → 800MB+).
        """
        self.pool_size = pool_size
        self.idle_timeout = idle_timeout
        self.max_uses = max_uses
        self._pool: Optional[asyncio.Queue] = None
        self._playwright: Optional[Playwright] = None
        self._initialized: bool = False
        self._last_used: dict[Browser, float] = {}
        self._usage_count: dict[Browser, int] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        
    async def initialize(self):
        """Inicializa el pool lanzando browsers."""
        if self._initialized:
            return
            
        try:
            self._playwright = await async_playwright().start()
            self._pool = asyncio.Queue(maxsize=self.pool_size)
            
            for _ in range(self.pool_size):
                browser = await self._playwright.firefox.launch(headless=True)
                self._last_used[browser] = time.time()
                self._usage_count[browser] = 0
                await self._pool.put(browser)
                
            self._initialized = True
        except Exception:
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    logger.debug("Error cerrando playwright")
            self._playwright = None
            self._pool = None
            self._initialized = False
            raise

    async def _close_idle_browser(self, browser: Browser) -> bool:
        """Cierra un browser inactivo. Retorna True si se cerró."""
        last_used = self._last_used.get(browser, 0)
        if time.time() - last_used > self.idle_timeout:
            try:
                await browser.close()
            except Exception:
                logger.debug("Error cerrando browser inactivo")
            self._last_used.pop(browser, None)
            return True
        return False

    async def _check_lifecycle(self, browser: Browser) -> bool:
        """Verifica health + max_uses. Retorna True si necesita relaunch.

        - Health check: ``browser.is_connected`` (detecta crash/OOM/segfault)
        - Max uses: recicla después de N usos para prevenir memory leak
        """
        needs_relaunch = False

        if not browser.is_connected:
            logger.warning("Browser desconectado — relanzando")
            needs_relaunch = True
        elif self._usage_count.get(browser, 0) >= self.max_uses:
            logger.info(
                f"Browser alcanzó max_uses={self.max_uses} — reciclando"
            )
            needs_relaunch = True

        if needs_relaunch:
            try:
                await browser.close()
            except Exception:
                logger.debug("Error cerrando browser para relaunch")
            self._last_used.pop(browser, None)
            self._usage_count.pop(browser, None)

        return needs_relaunch

    async def acquire(self) -> Browser:
        """Adquiere un browser del pool. Cierra inactivos sin bloquear el lock.

        Fix: el relaunch de un browser inactivo se hace FUERA del lock
        para no serializar los otros acquire() calls.
        """
        await self.initialize()

        # Fase 1: sacar browser del queue bajo lock
        async with self._lock:
            assert self._pool is not None, "pool no inicializado"
            browser = await self._pool.get()
            needs_relaunch = await self._close_idle_browser(browser) \
                or await self._check_lifecycle(browser)

        # Fase 2: relaunch FUERA del lock (puede tomar 3-5s)
        if needs_relaunch:
            assert self._playwright is not None, "playwright no inicializado"
            browser = await self._playwright.firefox.launch(headless=True)
            self._usage_count[browser] = 0

        # Fase 3: actualizar timestamp
        async with self._lock:
            self._last_used[browser] = time.time()

        return browser
        
    async def release(self, browser: Browser):
        """Libera un browser de vuelta al pool. Incrementa contador de usos."""
        async with self._lock:
            self._usage_count[browser] = self._usage_count.get(browser, 0) + 1
            self._last_used[browser] = time.time()
            assert self._pool is not None, "pool no inicializado"
            await self._pool.put(browser)
            
    async def close(self):
        """Cierra todos los browsers y detiene el pool."""
        if not self._initialized:
            return
                
        async with self._lock:
            while not self._pool.empty():
                try:
                    browser = self._pool.get_nowait()
                    await browser.close()
                except Exception:
                    logger.debug("Error cerrando pool")
                    
            if self._playwright:
                await self._playwright.stop()
            self._initialized = False
            self._last_used.clear()
            self._usage_count.clear()

    @property
    def stats(self) -> dict:
        """Stats del pool para monitoreo: tamaño, usage counts, connected."""
        return {
            "pool_size": self.pool_size,
            "max_uses": self.max_uses,
            "initialized": self._initialized,
            "tracked_browsers": len(self._usage_count),
        }


_pool_instance: Optional[BrowserPool] = None


def get_browser_pool() -> BrowserPool:
    """Retorna la instancia singleton del pool."""
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = BrowserPool()
    return _pool_instance


async def shutdown_browser_pool():
    """Cierra el pool global (útil para cleanup en tests/shutdown)."""
    global _pool_instance
    if _pool_instance:
        await _pool_instance.close()
        _pool_instance = None
