"""
utils/browser_pool.py
Pool de browsers Firefox para reutilizar instancias y eliminar overhead de 3-5s por trámite.
"""
import asyncio
import time
from typing import Optional

from playwright.async_api import Browser, Playwright, async_playwright


class BrowserPool:
    """
    Pool de browsers Firefox pre-lanzados.
    
    Características:
    - Pre-lanza N browsers al inicializar
    - Reutiliza browsers entre trámites (acquire/release)
    - Timeout de inactividad para cerrar browsers no usados
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
        self._cleanup_task: Optional[asyncio.Task] = None
        
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
            self._cleanup_task = asyncio.create_task(self._cleanup_idle())
        except Exception:
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
            self._playwright = None
            self._pool = None
            self._initialized = False
            raise
        
    async def _cleanup_idle(self):
        """Cierra browsers inactivos después de idle_timeout."""
        while self._initialized:
            await asyncio.sleep(60)
            now = time.time()
            
            browsers_to_check = []
            while not self._pool.empty():
                try:
                    browser = self._pool.get_nowait()
                    browsers_to_check.append(browser)
                except asyncio.QueueEmpty:
                    break
                    
            for browser in browsers_to_check:
                last_used = self._last_used.get(browser, 0)
                if now - last_used > self.idle_timeout:
                    try:
                        await browser.close()
                        del self._last_used[browser]
                    except Exception:
                        pass
                else:
                    await self._pool.put(browser)
                    
    async def acquire(self) -> Browser:
        """Adquiere un browser del pool."""
        await self.initialize()
        browser = await self._pool.get()
        self._last_used[browser] = time.time()
        return browser
        
    async def release(self, browser: Browser):
        """Libera un browser de vuelta al pool."""
        self._last_used[browser] = time.time()
        await self._pool.put(browser)
        
    async def close(self):
        """Cierra todos los browsers y detiene el pool."""
        if not self._initialized:
            return
            
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
                
        while not self._pool.empty():
            try:
                browser = self._pool.get_nowait()
                await browser.close()
            except Exception:
                pass
                
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
