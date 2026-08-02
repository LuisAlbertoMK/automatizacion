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

_(siguientes ciclos aquí)_
