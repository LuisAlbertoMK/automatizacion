# Benchmarks — Protocolo Mejora Autónoma v2

**Branch:** `experimento/mejora-autonoma-2026-08-05`  
**Fecha baseline:** 2026-08-05

## Definición de Métricas

| Métrica | Herramienta | Umbral objetivo |
|---------|------------|-----------------|
| Cobertura de tests | pytest --cov=src | ≥ 100% (actual 100%) |
| Tests pasando | pytest | 0 failures |
| Complejidad ciclomática | radon cc -s | Sin funciones E/D; Hotspots C → refactor |
| Tiempo de import (startup) | tiempo `import src.main` | ≤ 1s (baseline v1: ~0.97s) |
| Tiempo trámites secuenciales | browser_pool benchmark | ≤ 0.5s (baseline v1: ~0.35s) |
| Vulnerabilidades conocidas | pip-audit | 0 críticas/altas |
| Errores de lint (ruff) | ruff check | 0 |
| Errores de tipos (mypy) | mypy src/ | 0 |

## Baseline (HEAD en master — commit 0be2f4e)

| Métrica | Baseline |
|---------|----------|
| Tests pasando | 1056 passed, 0 failed |
| Cobertura | 100% (4180 stmts, 0 miss) |
| Complejidad avg | A (3.78) |
| Hotspots complejidad | `main.py:490 modo_interactivo` E(32), `nss.py:370 _obtener_nss` D(22), `orchestrator.py:445 modo_interactivo` D(30), `main.py:570 modo_directo` D(24) |
| pip-audit | No known vulnerabilities |
| ruff check | 0 errores |
| mypy | Configurado, exclude parcial |
| Startup time | ~1s (baseline v1) |
| --no-sandbox | ✅ condicional (requiere PLAYWRIGHT_NO_SANDBOX=true) |
| CORS | ✅ valida origen en prod |
| PBKDF2 salt | ✅ migrado a secrets.token_bytes(16) |
| DISABLE_API_AUTH | ✅ eliminado |
| Anthropic key validation | ⚠️ solo prefix check (C5 abierto) |
| PII en stdout (print) | ⚠️ M2 reportado (storage.py, free_captcha.py) |

## Presupuesto

- **Máx ciclos:** 5 (v2)
- **Máx tiempo por ciclo:** 5 min wall-clock (auto) / 10 min (humano)
- **Mínimo enfoques evaluados:** 10 (2 por ciclo)
- **Umbral de parada (mejora marginal decreciente):** < 2% de mejora en métrica benchmark → parar

## Tabla de Ciclos

| Ciclo | Gap atacado | Enfoques evaluados | Elegido | Métrica | Δ vs baseline | Δ vs ciclo anterior | Estado |
|-------|-------------|--------------------|---------|---------|---------------|---------------------|--------|
| Baseline | — | — | — | Ver tabla | — | — | ✅ |
| 1 | P3 (cache resultados) | A1, A2, A3 | **A1** (LRU+TTL singleton) | Tests: 1078, Cov: 99% (cache 100%), Complexity A(3.81) | +22 tests, cache.py 100% | — | ✅ done |
| 2 | P2 (async logger) | A1, A2, A3 | **A1** (QueueHandler stdlib) | Tests: 1084, Cov: 99.91% (logger 100%), zero event-loop block | +6 tests, logger.py 100% | -0.09% cov | ✅ done |
| 3 | P1 (browser pool health) | A1, A2, A3 | **A1** (is_connected + max_uses) | Tests: 1094, Cov: 99.91% (pool 100%) | +10 tests, pool.py 100% | +0% | ✅ done |
| 4 | M6 (deterministic salt) | A1, A2, A3 | **A1** (secrets.token_hex + migración) | Tests: 1104, Cov: 99.91% (storage 100%) | +10 tests, storage.py 100% | +0% | ✅ done |
| 5 | M2 (PII stdout) | A1, A2, A3 | **A1** (SANITIZE_STDOUT env) | Tests: 1110, Cov: 99.91% (logger 100%) | +6 tests (logger), configurable PII sanitization | +0% | ✅ done |
