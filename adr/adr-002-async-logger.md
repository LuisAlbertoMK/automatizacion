# ADR-002: Logger async sin bloqueo de event loop (P2)

**Fecha:** 2026-08-06  
**Estado:** ✅ Aceptada e implementada  
**Decisión:** Reemplazar `RotatingFileHandler` directo en `TramiteLogger` con `QueueHandler + QueueListener`
(pattern stdlib de Python), y añadir `TramiteMetrics.finish_async()` usando `asyncio.to_thread`.

## Contexto

Análisis original (ANALISIS-PERFORMANCE.md P2) identificó que `logging.handlers.RotatingFileHandler`
y `open().write()` en `TramiteMetrics.finish()` hacen I/O síncrono en el event loop. Cada `logger.info()`
bloquea ~1-5ms. En un trámite con cientos de log calls, eso se acumula.

## Opciones evaluadas

| # | Enfoque | Pros | Contras | ICE |
|---|---------|------|---------|-----|
| **A1 (elegido)** | QueueHandler + QueueListener (stdlib) | ✅ Cero deps nuevas, ✅ patrón estándar Python, ✅ QueueListener en thread background | ⚠️ Thread lifecycle en shutdown | 7×10×6 = 4.2 |
| **A2** | aiofiles para file writes | ✅ API async nativa, ✅ bien documentado | ❌ Nueva dep (~100KB), ❌ cambia todos los call sites a async | 6×8×3 = 1.4 |
| **A3** | Loguru (librería externa) | ✅ API elegante, ✅ async nativo, ✅ mejor DX | ❌ Reemplaza 100% del logging existente, ❌ riesgo de regresión | 5×7×2 = 0.7 |

## Decisión

**A1 — QueueHandler + QueueListener**: The standard Python pattern for non-blocking logging.
`QueueHandler` puts records into a `queue.Queue` (instant, no I/O), `QueueListener` runs
a background thread that does the actual file I/O via `RotatingFileHandler`.

### Cambios

1. **`TramiteLogger.__init__`**: Reemplaza `self._logger.addHandler(fh)` con `QueueHandler(queue)` +
   `QueueListener(queue, fh)` en background thread. File handler real accesible via `self._file_handler`.
2. **`TramiteMetrics`**: Añade `finish_async()` que usa `asyncio.to_thread(self._write_metric_to_file, record)`.
   Mantiene `finish()` sync para compatibilidad.
3. **Tests**: +6 tests async en `test_logger.py`. Fixture `_reset_tramite_cache` en conftest.py no afecta.

### Test compatibility

- Tests existentes que mock `log._logger.info()` siguen funcionando (el logger API no cambió).
- `test_init_json_format_from_env` verifica `self._file_handler.formatter` (no logger handlers).
- Tests async usan `asyncio_mode="auto"` (no necesitan `@pytest.mark.asyncio`).

## Consecuencias

- **Event loop no bloqueado** por log writes (QueueHandler es instantáneo).
- **TramiteMetrics.finish_async()** disponible para callers async (orchestrator, main).
- No se rompe ningún test existente (58 logger+cache tests, 1084 total).
- Coverage logger.py: 100%.
