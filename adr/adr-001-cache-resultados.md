# ADR-001: Cache de resultados de trámites (P3)

**Fecha:** 2026-08-06  
**Estado:** ✅ Aceptada e implementada  
**Decisión:** Implementar `TramiteCache` singleton LRU+TTL para evitar duplicación en `tramite_ambos` y `_ejecutar_ambos`.

## Contexto

`tramite_ambos()` en `main.py` y `_ejecutar_ambos()` en `orchestrator.py` ejecutan CURP + NSS secuencialmente sin reutilizar resultados. La v1 identificó que `tramite_ambos` duplica trabajo 100% (launch browser, CAPTCHA, scraping). ICE score: 3.6 (máximo gap priorizado).

## Decision

**Chosen:** A1 — TramiteCache singleton LRU+TTL

| Enfoque | Descripción | Ventajas | Desventajas | ICE |
|---------|-------------|----------|-------------|-----|
| **A1 (elegido)** | Singleton LRU+TTL in-memory, asyncio-safe | Simple, thread-safe, TTL configurable, patrón existing (`_fernet_cache` en storage.py) | Volatile (se pierde en restart), memoria limitada | 3.6 |
| **A2** | SQLite content-addressable | Persistente cross-session | Esfuerzo alto, sobreingeniería para use case actual | 1.4 |
| **A3** | Browser context reuse + cache híbrido | Maximiza reutilización | Confla con P1 (browser pool), riesgo alto | 0.8 |

## Consecuencias

- **Refactor commits** (comportamiento neutral): creación de `src/utils/cache.py`
- **Feat commits** (behavior change): integración en `main.py:tramite_ambos` y `orchestrator.py:_ejecutar_ambos`
- Cache hit muestra mensaje "desde cache"
- TTL default 30 min, LRU max 50 entries
- Tests: 22 tests unitarios en `test_cache.py` + fixture `_reset_tramite_cache` en conftest.py

## Referencias

- `src/utils/cache.py` — TramiteCache singleton
- `src/main.py:239-262` — tramite_ambos con cache
- `src/tramites/orchestrator.py:359-376` — _ejecutar_ambos con cache
- `tests/test_cache.py` — 22 tests, 100% coverage de cache.py
- `tests/conftest.py:_reset_tramite_cache` — fixture autouse para isolation
