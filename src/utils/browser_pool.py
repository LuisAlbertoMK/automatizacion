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
    
    def __init__(self, pool_size: int = 2, idle_timeout: int = 300):
        """
        Args:
            pool_size: Número de browsers a pre-lanzar (default: 2)
            idle_timeout: Segundos antes de cerrar browser inactivo (default: 300)
        """
        self.pool_size = pool_size
        self.idle_timeout = idle_timeout
        self._pool: Optional[asyncio.Queue] = None
        self._playwright: Optional[Playwright] = None
        self._initialized = False
        self._last_used: dict[Browser, float] = {}
        self._lock = asyncio.Lock()
        
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

    async def acquire(self) -> Browser:
        """Adquiere un browser del pool. Cierra inactivos lazy."""
        await self.initialize()
        async with self._lock:
            browser = await self._pool.get()
            # Lazy cleanup: si este browser está inactivo, crear uno nuevo
            if await self._close_idle_browser(browser):
                browser = await self._playwright.firefox.launch(headless=True)
            self._last_used[browser] = time.time()
            return browser
        
    async def release(self, browser: Browser):
        """Libera un browser de vuelta al pool."""
        async with self._lock:
            self._last_used[browser] = time.time()
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
