# ADR-003: Browser pool health checks + max_uses (P1)

**Fecha:** 2026-08-06  
**Estado:** ✅ Aceptada e implementada  
**Decisión:** Añadir `_check_lifecycle()` con `is_connected` health check + `max_uses` counter al `BrowserPool`.

## Contexto

ANALISIS-PERFORMANCE.md P1 identificó que el browser pool carece de:
- Health checks → browsers caídos (OOM, segfault) se devuelven al caller
- `max_uses` → browsers crecen de 200MB a >800MB por cookies/cache/sesiones acumuladas
- Context recycling → sin límite de usos por browser

## Opciones evaluadas

| # | Enfoque | Pros | Contras | ICE |
|---|---------|------|---------|-----|
| **A1 (elegido)** | max_uses counter + is_connected check en acquire() | ✅ Simple, ✅ bajo riesgo, ✅ stats property | ⚠️ No detecta browsers congelados (is_connected=True pero unresponsive) | 7×10×6 = 4.2 |
| **A2** | Background monitoring thread + metrics (crash_count, restart_count) | ✅ Detección proactiva, ✅ observabilidad | ❌ Thread lifecycle complexity | 6×8×4 = 1.9 |
| **A3** | Pool de BrowserContext (no browser-level) | ✅ Context recycling más fino | ❌ Requiere refactor de base.py, conflora con P1 | 5×7×3 = 1.1 |

## Decisión: A1

### Cambios en `src/utils/browser_pool.py`:
1. `__init__`: añade `max_uses: int = 10` y `self._usage_count: dict[Browser, int]`
2. `initialize()`: inicializa `_usage_count[browser] = 0` para cada browser nuevo
3. `_check_lifecycle(browser)`: 
   - Health check: `browser.is_connected` → si False, cierra + retorna True (relaunch)
   - Max uses: `self._usage_count.get(browser, 0) >= self.max_uses` → cierra + retorna True
4. `acquire()`: `needs_relaunch = _close_idle_browser() or _check_lifecycle()`; nuevo browser → `_usage_count[browser] = 0`
5. `release()`: incrementa `_usage_count[browser]`
6. `stats` property: expone pool_size, max_uses, initialized, tracked_browsers

### Tests (`tests/test_browser_pool.py` — +10 tests):
- max_uses default y custom
- usage_count initialized a 0
- _check_lifecycle: disconnected, max_uses exceeded, healthy
- release increments count
- acquire relaunches on disconnect
- acquire relaunches on max_uses
- stats property
- close clears usage_count

## Consecuencias
- Browser zombies (OOM/segfault) detectados antes de uso → relaunch automático
- Memory leak prevenido: browser reciclado cada 10 usos → RAM estable
- stats property permite monitoreo de pool health
- No breaking changes en API (configuración opcional con default)
- 32 browser_pool tests, 100% coverage
