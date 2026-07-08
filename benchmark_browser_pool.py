"""
Benchmark: Browser Pool vs Legacy (sin pool)
Mide el overhead de launch/close browser en trámites secuenciales.
"""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch


async def benchmark_legacy(num_tramites: int = 3):
    """Benchmark del comportamiento legacy (sin pool)."""
    from src.modules.base import BaseModule
    
    print(f"\n{'='*60}")
    print(f"BENCHMARK LEGACY (sin pool) - {num_tramites} trámites")
    print(f"{'='*60}")
    
    module = BaseModule(captcha_solver=None, use_ocr=False, name="Benchmark")
    
    start = time.time()
    
    for i in range(num_tramites):
        print(f"\nTrámite {i+1}/{num_tramites}:")
        t0 = time.time()
        
        mock_pw = AsyncMock()
        mock_firefox = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        mock_firefox.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_pw.firefox = mock_firefox
        mock_browser.close = AsyncMock()
        mock_context.close = AsyncMock()
        mock_page.close = AsyncMock()
        mock_pw.__aexit__ = AsyncMock()
        
        with patch("modules.base.async_playwright", return_value=mock_pw):
            p, browser, page = await module.launch_browser()
            t_launch = time.time() - t0
            print(f"  launch_browser: {t_launch:.3f}s")
            
            await asyncio.sleep(0.1)
            
            t_close = time.time()
            await module.close_browser(p, browser)
            t_close = time.time() - t_close
            print(f"  close_browser:  {t_close:.3f}s")
    
    total = time.time() - start
    print(f"\n{'='*60}")
    print(f"Total: {total:.3f}s")
    print(f"Promedio por trámite: {total/num_tramites:.3f}s")
    print(f"{'='*60}\n")
    
    return total


async def benchmark_pool(num_tramites: int = 3):
    """Benchmark del comportamiento con pool."""
    from src.modules.base import BaseModule
    from src.utils.browser_pool import get_browser_pool, shutdown_browser_pool
    
    print(f"\n{'='*60}")
    print(f"BENCHMARK CON POOL - {num_tramites} trámites")
    print(f"{'='*60}")
    
    await shutdown_browser_pool()
    
    module = BaseModule(captcha_solver=None, use_ocr=False, name="Benchmark")
    
    start = time.time()
    
    for i in range(num_tramites):
        print(f"\nTrámite {i+1}/{num_tramites}:")
        t0 = time.time()
        
        mock_pw = AsyncMock()
        mock_firefox = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        mock_firefox.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_pw.firefox = mock_firefox
        mock_browser.close = AsyncMock()
        mock_context.close = AsyncMock()
        mock_page.close = AsyncMock()
        mock_pw.__aexit__ = AsyncMock()
        
        with patch("utils.browser_pool.async_playwright", return_value=mock_pw):
            pool = get_browser_pool()
            await pool.initialize()
            
            p, browser, page = await module.launch_browser()
            t_launch = time.time() - t0
            print(f"  launch_browser: {t_launch:.3f}s")
            
            await asyncio.sleep(0.1)
            
            t_close = time.time()
            await module.close_browser(p, browser)
            t_close = time.time() - t_close
            print(f"  close_browser:  {t_close:.3f}s")
    
    total = time.time() - start
    print(f"\n{'='*60}")
    print(f"Total: {total:.3f}s")
    print(f"Promedio por trámite: {total/num_tramites:.3f}s")
    print(f"{'='*60}\n")
    
    await shutdown_browser_pool()
    
    return total


async def benchmark_real_world():
    """Simula escenario real: 3 trámites secuenciales."""
    from src.modules.base import BaseModule
    from src.utils.browser_pool import shutdown_browser_pool
    
    print(f"\n{'='*60}")
    print("BENCHMARK REAL WORLD - 3 trámites secuenciales")
    print(f"{'='*60}")
    
    await shutdown_browser_pool()
    
    module = BaseModule(captcha_solver=None, use_ocr=False, name="RealWorld")
    
    print("\nCon pool (primera vez - incluye inicialización):")
    t0 = time.time()
    
    mock_pw = AsyncMock()
    mock_firefox = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()
    
    mock_firefox.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_pw.firefox = mock_firefox
    mock_browser.close = AsyncMock()
    mock_context.close = AsyncMock()
    mock_page.close = AsyncMock()
    mock_pw.__aexit__ = AsyncMock()
    
    with patch("utils.browser_pool.async_playwright", return_value=mock_pw):
        for i in range(3):
            p, browser, page = await module.launch_browser()
            await asyncio.sleep(0.1)
            await module.close_browser(p, browser)
    
    t_pool = time.time() - t0
    print(f"  Total: {t_pool:.3f}s")
    
    await shutdown_browser_pool()
    
    print("\nSin pool (legacy):")
    t0 = time.time()
    
    with patch("modules.base.async_playwright", return_value=mock_pw):
        for i in range(3):
            p, browser, page = await module.launch_browser()
            await asyncio.sleep(0.1)
            await module.close_browser(p, browser)
    
    t_legacy = time.time() - t0
    print(f"  Total: {t_legacy:.3f}s")
    
    mejora = ((t_legacy - t_pool) / t_legacy) * 100
    print(f"\n{'='*60}")
    print(f"Mejora: {mejora:.1f}%")
    print(f"Tiempo ahorrado: {t_legacy - t_pool:.3f}s")
    print(f"{'='*60}\n")
    
    return t_legacy, t_pool


async def main():
    print("\n" + "="*60)
    print("BROWSER POOL BENCHMARK")
    print("="*60)
    
    t_legacy = await benchmark_legacy(3)
    t_pool = await benchmark_pool(3)
    
    print("\n" + "="*60)
    print("COMPARACIÓN FINAL")
    print("="*60)
    print(f"Legacy (sin pool): {t_legacy:.3f}s")
    print(f"Con pool:          {t_pool:.3f}s")
    
    if t_legacy > 0:
        mejora = ((t_legacy - t_pool) / t_legacy) * 100
        print(f"Mejora:            {mejora:.1f}%")
    
    print("="*60 + "\n")
    
    await benchmark_real_world()


if __name__ == "__main__":
    asyncio.run(main())
