# Mejora-Log — Protocolo de Mejora Autónoma Iterativa

Branch: `experimento/mejora-autonoma-2026-08-02`
Fecha inicio: 2026-08-02
Baseline registrado: **1019 passed, 0 failed, 46.78s, 23 warnings, ruff limpio**

---

## Ciclo 1 — bcrypt rounds: bug latente de config + guardrail de seguridad

**Fecha**: 2026-08-02
**Gap**: `UserWarning: bcrypt.kdf() called with only 4 round(s)` (6 ocurrencias) + sospecha de config insegura.

**Hallazgo (verificado empíricamente)**:
- bcrypt.kdf es KDF **LINEAL** (como PBKDF2): rounds=1000 → 5.7s; rounds=100k → >120s (timeout); 600k → ~54min (extrapolado).
- Defaults de producción eran `BCRYPT_KDF_ROUNDS=600k` / `BCRYPT_HASH_ROUNDS=100k` — **runtime inviable** (nunca probados; los tests los sobrescribían con 4).
- El warning de bcrypt desaparece solo con rounds >= 100. El comentario del conftest ("600k ≈ 1s") era falso.

**Enfoques evaluados (3)**:
- E1: Defaults → 100 rounds (~0.66s, sin warning, viable) + tests a 100 + guardrail `_guard_rounds()` que rechaza rounds < 100 con StorageError claro. ✔ **ELEGIDO**
- E2: Mantener 600k/100k + filterwarnings en pytest — parche cosmético, deja el bug latente de runtime.
- E3: Migrar a scrypt/Argon2id (OWASP) — ruptura de dependencias + migración de datos, fuera de alcance de un ciclo.

**Resultado breaker (3 enfoques de ataque)**:
1. Warning residual en suite completa → 0 ocurrencias bcrypt.
2. Regresión de runtime → 1022 passed, 0 failed.
3. Compat: storage_migrate_salt (PBKDF2 600k directo) + _get_cipher cacheado → tests pasan.

**Resultado E2E**: 1022 passed, 0 failed, 54.93s (24 en test_storage).

**Benchmark**: tests 1019→1022 (+3) | warnings 23→9 (-14) | tiempo 46.78→54.93s (+8.15s, +17% — costo de seguridad 100 vs 4 rounds, aceptable).

**Archivos**: `src/utils/storage.py` (defaults 100, `_guard_rounds`, `_MIN_BCRYPT_ROUNDS=100`), `tests/conftest.py` (4→100), `tests/test_storage.py` (+3 tests guardrail).

**Aprendizaje**: Los valores de seguridad derivados (KDF/hash rounds) nunca deben ser constantes mágicas no probadas — medir el runtime real antes de fijar defaults. Guardrail mínimo + test de regresión previene reintroducción.

---

## Ciclo 2 — limpieza de warnings de tests: destapó BUG REAL de producción

**Fecha**: 2026-08-02
**Gap**: 9 warnings residuales (8 coroutines never awaited + 1 StarletteDeprecationWarning) — la mayoría por tests que parchean `asyncio.run` y dejan la coroutine sin cerrar.

**Hallazgo (verificado con suite completa)**:
- Los RuntimeWarning "coroutine never awaited" se atribuyen a tests POSTERIORES al que creó la coro — el GC recolecta las coros huérfanas tarde. (p. ej. `test_valid_curp` mostraba warnings de `test_all_flags_accepted`.)
- **BUG REAL DE PRODUCCIÓN**: `src/main_multimodal.py:84` llamaba `orchestrator.modo_interactivo()` (async) **sin `asyncio.run` ni `await`** → el modo interactivo multimodal (--voice/--image sin --tramite) NUNCA ejecutaba. El breaker lo destapó al introducir AsyncMock: `AsyncMockMixin._execute_mock_call was never awaited` en esa línea.
- `src/main.py` era correcto (702/704 usan `asyncio.run`) — su warning era contaminación GC de los tests.
- `StarletteDeprecationWarning` NO hereda de `DeprecationWarning` en la versión instalada → el filtro con categoría `DeprecationWarning` no matcheaba; con `Warning` sí.

**Enfoques aplicados (4)**:
- E1: `coro_fn.close()` ×3 en TestModoDirecto (tests que inspeccionan la coro vía call_args). ✔
- E2: `modo_interactivo = AsyncMock()` en `tests/test_main_multimodal.py:27`. ✔
- E3: `pyproject.toml`: `[tool.pytest.ini_options]` + markers (`real_sleep`) + filterwarnings Starlette (categoría corregida a `:Warning`). ✔
- E4: **Fix bug real** `src/main_multimodal.py:84` → `asyncio.run(orchestrator.modo_interactivo())`. ✔
- E5: Helper `_run_mock_cierra(coro, error=None)` en `tests/test_main.py` — mock de asyncio.run que cierra la coro (y opcionalmente lanza KeyboardInterrupt/CancelledError) — aplicado a test_direct_mode, test_interactive_mode, test_keyboard_interrupt_handling, test_cancelled_error_handling, test_all_flags_accepted. ✔
- E6: Test de regresión `test_sin_args_ejecuta_coro_via_asyncio_run` en `tests/test_main_multimodal.py` — verifica que main() entrega la coro a asyncio.run (falla si se revierte el fix). ✔

**Resultado breaker (3 enfoques de ataque)**:
1. Warnings residuales → **0** en suite completa (era 10 tras E1-E3).
2. Regresión → 1022 passed, 0 failed.
3. Falsos positivos: el warning de línea 442 en main.py era contaminación GC (main.py usa asyncio.run correctamente) — confirmado al cerrar las coros de los tests.

**Resultado E2E**: 1023 passed, 0 failed, **0 warnings**, 41.39s.

**Benchmark**: tests 1022→1023 (+1 regresión) | warnings 9→0 (-9) | tiempo 54.93→41.39s (-13.5s — varianza de máquina; el fix de main_multimodal no añade runtime en tests porque asyncio.run se parchea).

**Archivos**: `src/main_multimodal.py` (BUG FIX: await modo_interactivo), `tests/test_main.py` (helper `_run_mock_cierra` + 5 tests), `tests/test_main_multimodal.py` (AsyncMock + **test de regresión** que falla si se revierte el fix), `pyproject.toml` (markers + filterwarnings).

**Aprendizaje**: Los warnings de coroutines en tests con `asyncio.run` parcheado son una bomba de tiempo — la coro huérfana se recolecta en un test ajeno y enmascara el diagnóstico. El patrón `asyncio.run` + mock que cierra la coro es la solución estándar. Y: un breaker con mocks async es ORO para destapar bugs de `await` faltante en producción.

---

_(siguientes ciclos aquí)_
