# Análisis v2 — agente-tramites-gobmx

**Fecha:** 2026-08-06  
**Branch:** `experimento/mejora-autonoma-2026-08-05`  
**Score v1:** Mejoras de julio/algebra ya mergeadas a master

## Cross-Reference: Gaps del análisis original vs. estado actual

### FIXED (4 findings — ya no accionables)

| ID | Finding | File:Line | Por qué está fixed |
|----|---------|-----------|-------------------|
| C1 | `--no-sandbox` en Playwright | `base.py:186-187` | Ahora condicional: `PLAYWRIGHT_NO_SANDBOX=true` env var |
| C2 | CORS `allow_origins="*"` | `api.py:234-243` | Production raises `RuntimeError` si CORS_ORIGINS no configurado |
| C3 | Salt estático en PBKDF2 | `storage.py:57-70,86-95` | Migrado a `secrets.token_bytes(16)` + migración automática |
| C4 | `DISABLE_API_AUTH` env override | `api.py:128-160` | Variable eliminada; API_KEY obligatoria en startup |

### OPEN / PARTIAL Gaps (sorted por ICE desc)

| # | ID | Description | File:Line | Status | Impact(1-10) | Conf(1-10) | Ease(1-10) | ICE |
|---|----|-------------|----------|--------|-------------|------------|------------|-----|
| 1 | P3 | Sin cache de resultados; tramite_ambos duplica trabajo 100% | `main.py:220-262`, `orchestrator.py:349-380` | OPEN | 6 | 10 | 6 | **3.6** |
| 2 | P2 | I/O síncrono en event loop: RotatingFileHandler + open().write() | `logger.py:67-79,158-160` | OPEN | 6 | 10 | 5 | **3.0** |
| 3 | P1 | Browser pool sin health checks, max_uses, context recycling | `browser_pool.py` | OPEN | 7 | 10 | 4 | **2.8** |
| 4 | M6 | Salt hash determinístico derivado del alias | `storage.py:142` | OPEN | 5 | 10 | 5 | **2.5** |
| 5 | M2 | PII exfiltrable via stdout: print() unsanitized | `logger.py:95-98`; `nss.py:167,394,406,444,455`; `curp.py:355`; etc | OPEN | 8 | 10 | 3 | **2.4** |
| 6 | COMP-1 | `modo_interactivo` complejidad E(32) | `main.py:490` | OPEN | 5 | 10 | 4 | **2.0** |
| 7 | P4 | Sin requests.Session reuse (8 call sites) | `captcha.py`, `base.py`, `nss.py`, etc | OPEN | 5 | 10 | 4 | **2.0** |
| 8 | C5 | Anthropic key validada solo por prefix `sk-ant-` | `claude.py:55` | OPEN | 5 | 10 | 3 | **1.5** |
| 9 | M4 | Audio challenge URL sin validación https/domain (SSRF) | `free_captcha.py:235-241` | OPEN | 5 | 10 | 3 | **1.5** |
| 10 | P5 | Whisper no pre-warmed en __init__ | `free_captcha.py:66-73` | PARTIAL | 4 | 10 | 4 | **1.6** |
| 11 | M5 | `exc_info=True` escribe traceback unsanitized | `api.py:340,359` | OPEN | 4 | 10 | 4 | **1.6** |
| 12 | M3 | PDF path no validado en subprocess.run | `base.py:562-564` | PARTIAL | 3 | 9 | 5 | **1.4** |
| 13 | M1 | IMAP sin contexto SSL explícito | `mail_reader.py:55` | PARTIAL | 3 | 9 | 4 | **1.1** |
| 14 | M7 | No SHA-256 checksum en PDF downloads | `base.py:501-550` | OPEN | 4 | 8 | 4 | **1.3** |

## ICE Scoring

Fórmula: Ice = Impact(1-10) × Confidence(1-10) × Ease(1-10) / 100
- **Impact**: cuánto afecta el negocio/correctitud
- **Confidence**: cuánto estoy seguro de la medición
- **Ease**: qué tan fácil de implementar (5 = fácil, 1 = imposible)

## Top 5 prioritarios para v2

| Rank | Gap | ICE | Razon |
|------|-----|-----|-------|
| 1 | P3 (cache resultados) | 3.6 | Elimina duplicación 100% en tramite_ambos. Alto impacto, bajo esfuerzo |
| 2 | P2 (async logger) | 3.0 | Bloquea event loop. Refactor a aiofiles |
| 3 | P1 (browser pool health) | 2.8 | Previene OOM/segfault. Alto impacto, esfuerzo medio |
| 4 | M6 (deterministic salt) | 2.5 | Debilidad criptográfica. Pequeño fix en storage.py |
| 5 | M2 (PII stdout) | 2.4 | Fuga de PII. Alto impacto, requiere tocar muchos archivos |

## Trend vs. Análisis v1 (2026-07-08)

- **C1-C4**: ✅ Todos FIXED en v1 (no volver a tocar)
- **C5**: ⚠️ Sigue OPEN — validation por prefix solamente
- **P1-P5**: 4/5 still OPEN (solo P3 parcialmente addressed por browser_pool)
- **M1-M7**: 6/7 still OPEN (M2 es el más crítico)
