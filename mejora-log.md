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

## Ciclo 3 — dead code + cobertura: template.py eliminado, control_confianza 26%→100%

**Fecha**: 2026-08-02
**Gap**: coverage mostró 2 módulos con cobertura artificialmente baja: `control_confianza.py` 26% y `template.py` 0%.

**Hallazgo (verificado con coverage + grep)**:
- `src/tramites/template.py` era **código muerto**: solo se auto-referencia (docstring "TEMPLATE para crear nuevos módulos"). Ningún import en src/, 0% cobertura. README lo listaba en 2 lugares (tree de archivos + feature F4).
- `control_confianza.py`: los 4 tests del fail-fast YA existían y cubrían el flujo real — el 26% era **110 líneas inalcanzables** (todo el flujo navegable `_run` + 30 líneas post-`raise` de línea 68). El portal está muerto desde 2025 (DNS dead) → ese código nunca podrá ejecutarse. Dead code real, no falta de tests.

**Enfoques aplicados (3)**:
- E1: `git rm src/tramites/template.py` — eliminación de módulo plantilla muerto. ✔
- E2: `src/tramites/control_confianza.py` — eliminación del flujo inalcanzable tras el fail-fast (`_run` completo + try/except + lógica de llenado) → módulo queda fail-fast puro (68 líneas vs 180). El registro en orchestrator (TRAMITES_REGISTRADOS + ejecutar_tramite) sigue intacto: `consultar()` mantiene validación de CURP + raise con mensaje CECC. ✔
- E3: README.md — actualización de las 2 referencias a template.py (línea 121 tree + fila F4 de features). ✔

**Resultado breaker (3 enfoques de ataque)**:
1. Regresión → 1023 passed, 0 failed.
2. Warnings → 0 (sin reintroducción).
3. Integridad del registro → orchestrator importa y registra ControlConfianzaModule sin problema (suite test_orchestrator + test_control_confianza pasan).

**Resultado E2E**: 1023 passed, 0 failed, **0 warnings**, 43.28s.

**Benchmark**: tests 1023→1023 (0) | warnings 0→0 | cobertura 91.88→**93.25%** (+1.37) | control_confianza 26→100% | template 0% (eliminado).

**Archivos**: `src/tramites/template.py` (eliminado), `src/tramites/control_confianza.py` (−112 líneas dead code), `README.md` (2 refs).

**Aprendizaje**: Un módulo cuyo servicio externo murió no debería conservar el flujo navegable como dead code tras un fail-fast — confunde a cobertura y a futuros mantenedores. La cobertura baja NO siempre significa "faltan tests": a veces significa "sobra código". Verificar inalcanzabilidad antes de escribir tests.

---

## Ciclo 4 — cobertura main.py 72%→92%: tests de orquestación y dispatch

**Fecha**: 2026-08-02
**Gap**: `src/main.py` al 72% (131 líneas sin cubrir) — el más bajo de la tabla tras eliminar el dead code del ciclo 3. Los métodos `tramite_rfc/acta/pasaporte/semanas/control_confianza/buro/circulo/cita_ine/cita_sat` (267-377) y el dispatch REPL (517-533) no tenían tests directos.

**Hallazgo (verificado con coverage --term-missing)**:
- Los 9 métodos `tramite_*` orquestan módulos YA cubiertos al 100% — la falta de cobertura era de los TESTS, no del código.
- `_validar_rfc`/`_validar_email` (estáticos) también sin cubrir.
- El dispatch REPL solo testaba 3 comandos (curp/nss/ambos) — 9 comandos más (rfc, acta, pasaporte, semanas, control/confianza, buro, circulo, ine, sat) sin cobertura.

**Enfoques aplicados (3)**:
- E1: `TestTramitesSimples` — 14 tests de los 9 métodos `tramite_*` (con perfil, sin perfil, y los que siempre piden datos) vía helper `_tramite()` que mockea el módulo destino + `builtins.input`. Cubre 267-377. ✔
- E2: `TestValidarRfcEmail` — 4 tests de los validadores estáticos (ok + inválido). Cubre 453-467. ✔
- E3: `test_comando_dispatch` parametrizado (15 casos: 9 comandos + 6 aliases) en `TestModoInteractivo` + `test_cita_sat_curp_invalida` (rama de CURP inválida 371-372). Cubre 517-533. ✔

**Resultado breaker (3 enfoques de ataque)**:
1. Regresión → 1056 passed, 0 failed (suite completa).
2. Warnings → 0 (los 33 tests nuevos no introducen coroutines ni warnings).
3. Falsos positivos → los tests no tocaron código de producción (solo tests/test_main.py) — riesgo de regresión mínimo, confirmado con suite completa.

**Resultado E2E**: 1056 passed, 0 failed, **0 warnings**, 45.01s.

**Benchmark**: tests 1023→1056 (+33) | warnings 0→0 | cobertura 93.25→**95.53%** (+2.28) | main.py 72→**92%** | tiempo 43.28→45.01s (+1.7s, varianza).

**Archivos**: `tests/test_main.py` (TestTramitesSimples +14, TestValidarRfcEmail +4, test_comando_dispatch +15, test_cita_sat_curp_invalida +1 = +34 tests, −1 del helper).

**Aprendizaje**: La cobertura de un CLI no se mide por los módulos (ya cubiertos), sino por los MÉTODOS de orquestación y su dispatch. Un test parametrizado por comando del REPL es la forma más barata de cubrir el enrutamiento completo. Los métodos `tramite_*` son "glue code" de 2 patrones (con perfil / _pedir_dato) — un helper único los cubre todos.

---

## Resumen del protocolo (4 ciclos)

| Ciclo | Enfoques | Resultado | Benchmark |
|---|---|---|---|
| 1 | 3 (bcrypt) | Guardrail rounds 100 + fix config | 1019→1022 tests, warnings 23→9 |
| 2 | 6 (warnings) | 0 warnings + **BUG REAL fix** main_multimodal | 1023 tests, warnings 9→0 |
| 3 | 3 (dead code) | template.py eliminado, control_confianza 100% | cobertura 91.88→93.25% |
| 4 | 3 (cobertura CLI) | main.py 92%, dispatch REPL cubierto | 1023→1056 tests, cobertura 95.53% |
| **Total** | **15 enfoques** (≥10 requeridos) | Breaker sobrevive en todos los ciclos | 1056 passed, 0 warnings, 95.53% |

**Criterios de parada**: sin gaps detectables (cobertura ≥ 88% en todo módulo activo, salvo main.py 92% por cv/escrito DOCUMENTOS_AVAILABLE + menú interactivo), breaker superado ×4, 100% tests pasan, benchmark ≥ previo en cada ciclo. **Protocolo completo.**

_(siguientes ciclos aquí)_

## RONDA 2 - Ciclo 1 (cobertura voice_input/ocr)

**Branch**: experimento/mejora-autonoma-2026-08-02-b2 (desde dde7e84 en main) | **Modo**: auto | **Commit**: e88bcd6

**Analisis** (ciclo 1): gap priorizado = cobertura baja en `src/utils/voice_input.py` (85%) y `src/utils/ocr.py` (88%). Baseline ronda: 1056 passed, 0 warnings, 45.01s, cobertura global 95.53%.

**Enfoques aplicados (3)**:
- **E1 (ocr.py)**: +7 tests en `TestCacheLRU`/preprocess — cache hit, LRU eviction con hit, PDF inexistente (getmtime OSError -> sin cache), PDF cache hit, PermissionError, upscale <1000px, downscale >2000px.
- **E2 (voice_input.py)**: +2 tests — countdown (3 sleeps 97-101), curp detectada devuelta directo.
- **E3**: pragma `no cover` en `test_voice_input()` (script demo manual con microfono, no testeable en CI).

**BUG REAL encontrado (via gap de cobertura)**: el cache LRU de OCRExtractor nunca movia la entrada al final en un cache hit (extract_from_bytes/pdf manejaban el hit directo, saltandose `_cache_result`). La eviction era por orden de INSERCION, no por uso. Fix: todos los hits pasan ahora por `_cache_result` -> `move_to_end`. Regresion que la cobertura detecto como linea 54 inalcanzable.

**Dead code eliminado**: rama 'CURP con formato invalido' en `get_curp_interactive` (voice_input.py) — inalcanzable por invariante: `extract_curp` usa la misma regex que `_validar_curp` ([HM] obligatorio en pos 11), toda CURP extraida es siempre valida. Simplificado a `if curp: return curp`.

**Resultado breaker (3 ataques)**: (1) suite completa 1066 passed EXIT=0, (2) 0 warnings, (3) ruff clean src/ + tests/.

**Resultado E2E**: 1066 passed (+10), 0 failed, 0 warnings, 82.46s (con --cov global, no comparable con baseline sin cov).

**Benchmark**: tests 1056->1066 (+10) | warnings 0->0 | cobertura global 95.53->**96.44%** (+0.91) | ocr 88->**100%** | voice_input 85->**100%**.

**Archivos**: `src/utils/ocr.py` (fix LRU real, 4 lineas), `src/utils/voice_input.py` (refactor rama dead, 11 lineas), `tests/test_ocr.py` (+7), `tests/test_voice_input.py` (+2).

**Aprendizaje**: un gap de cobertura persistente tras escribir el test 'obvio' casi siempre es (a) un test mal dirigido (la linea apuntada no es la que crees — verificar con Get-Content la linea exacta) o (b) dead code real. En ocr.py los 3 tests iniciales apuntaban a lineas equivocadas: la 181-183 era el downscale (>2000px) no el upscale, la 129-131 era cache hit de PDF (no el OSError), y la 54 (move_to_end) era inalcanzable por diseno roto del LRU. Leer el codigo real antes de escribir el test evita 2 ciclos de ida y vuelta.

--- 
_(fin ronda 2 ciclo 1 — siguiente ciclo: gaps restantes pii.py 96%, validators.py 97%, y main.py cv/escrito DOCUMENTOS_AVAILABLE + menu interactivo 612-679)_
