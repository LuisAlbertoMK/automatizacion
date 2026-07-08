# Análisis de Performance y Eficiencia

**Proyecto:** agente-tramites-gobmx  
**Fecha:** 2026-07-08  
**Analista:** Señor Arquitecto (subagente especializado)

---

## Cuellos de Botella Críticos

### 🔴 P1 — Browser Pool sin health checks ni límite de contexto

**Archivo:** `src/utils/browser_pool.py`

- Cada `acquire()` crea nuevo `context` + `page` sin reiniciar el browser
- El contexto acumula cookies/cache/sesiones → memory leak lento
- Sin `max_uses` por browser — Firefox puede crecer de 200MB a >800MB
- Sin detección de browsers caídos (OOM, segfault)

### 🔴 P2 — Logging con I/O síncrono en el event loop

**Archivo:** `src/utils/logger.py:130-136`, `base.py:78-96`

Cada `logger.info()`, `metrics.finish()` y `print()` hace escritura síncrona a disco:
- `open(...).write(...)` bloquea ~1-5ms
- Sin rotación de logs → `tramites.log` crece infinito

### 🔴 P3 — Sin caché de resultados de trámites

Cada llamada duplica el trabajo: launch browser, captcha, scraping, PDF.
- `tramite_ambos()` ejecuta CURP dos veces completas
- Sin caché de CAPTCHA resuelto (misma imagen podría resolverse dos veces)
- Ahorro potencial: ~15-30s por operación duplicada

### 🔴 P4 — Pool HTTP sin reuso de sesión

**Archivos:** `captcha.py:80`, `base.py:292-296`, `nss.py:251-256`

Cada request usa `requests.get/post` sin sesión:
- Sin connection pooling (TCP + TLS handshake en cada request)
- Sin keep-alive
- Múltiples resolución DNS

### 🔴 P5 — Whisper carga modelo en hot path + CPU

**Archivo:** `src/utils/free_captcha.py:232-236`

`whisper.load_model("base")` bajo demanda en el flujo CAPTCHA:
- ~334MB RAM para modelo "base"
- 3-10s de startup en el momento crítico
- Sin verificación de GPU (probablemente CPU)

---

## Recomendaciones de Optimización

### 🥇 P1 — Urgente (impacto alto, esfuerzo bajo-medio)

| # | Recomendación | Archivos | Esfuerzo | Impacto |
|---|---------------|----------|----------|---------|
| 1 | Cache LRU de resultados (compartir entre módulos) | main.py, orchestrator.py | 1 día | Elimina duplicación 100% |
| 2 | Browser pool: health check + max_uses | browser_pool.py, base.py | 2 días | Previene OOM |
| 3 | requests.Session para HTTP pooling | captcha.py, base.py, nss.py | 0.5 día | -30-50% latencia red |
| 4 | Logger async con aiofiles | logger.py | 1 día | Elimina bloqueo event loop |
| 5 | Whisper warmup en __init__ | free_captcha.py | 0.5 día | Elimina 5-15s startup |

### 🥈 P2 — Importante (impacto medio-alto)

| # | Recomendación | Esfuerzo |
|---|---------------|----------|
| 6 | Log rotation (RotatingFileHandler 100MB x 5) | 0.5 día |
| 7 | Parallelizar tramite_ambos con asyncio.gather() | 1 día |
| 8 | Bloquear recursos innecesarios en Playwright (page.route) | 0.5 día |
| 9 | Pool de contexts (no solo browsers) | 2 días |
| 10 | Log levels configurables en producción | 0.5 día |

### 🥉 P3 — Deseable

| # | Recomendación |
|---|---------------|
| 11 | Reemplazar Tesseract por EasyOCR/PaddleOCR con GPU |
| 12 | aiohttp en vez de requests + to_thread |
| 13 | PDF processing lazy + page limit + PyMuPDF |
| 14 | Comprimir screenshots de debug |
| 15 | Pool de conexiones IMAP persistente |

---

## Benchmarks Existentes

Solo existe `benchmark_browser_pool.py` y usa MOCKS que no son representativos:

| Benchmark | Qué mide | Limitación |
|-----------|----------|------------|
| benchmark_legacy() | Tiempo launch + close sin pool | AsyncMock, sin latencia real |
| benchmark_pool() | Tiempo acquire + release con pool | AsyncMock, sin latencia real |
| benchmark_real_world() | Pool vs no-pool en 3 trámites | asyncio.sleep(0.1) simulado |

**Lo que NO se mide:** RAM real de Firefox, tiempo de CAPTCHA real, tasa de fallo por portal, throughput, cold/warm start.

---

## Mapa Térmico por Módulo (estimado)

| Módulo | Tiempo | RAM | Cuello de botella |
|--------|--------|-----|-------------------|
| CURP | 15-30s | 300-500MB | CAPTCHA + PDF |
| NSS | 30-60s | 300-500MB | reCAPTCHA (15-45s) + IMAP |
| RFC | ~30s | 250-400MB | Navegación SAT + CAPTCHA |
| Acta | 30-60s | 300-500MB | RENAPO timeout + PDF |
| Pasaporte | 2-5min | 300-500MB | SRE + reCAPTCHA |
| Control Confianza | 10-30min | 300-500MB | Intervención manual |
| Buró/Círculo | 5-10min | 300-500MB | Portal lento + CAPTCHA |

---

## Métricas Sugeridas para Monitoreo

| Categoría | Métrica | Threshold |
|-----------|---------|-----------|
| Browser Pool | browsers activos | ≤ pool_size |
| Browser Pool | RAM por proceso Firefox | < 500MB |
| Browser Pool | crash count | 0/hora |
| Latencia | tiempo total por trámite | < 120s |
| Captcha | tasa de éxito 2captcha | > 90% |
| Captcha | tiempo promedio resolución | < 30s |
| Captcha | tasa de fallo FreeCaptcha | < 30% |
| Eficiencia | trámites por hora | > 20/h |
| Storage | log file size | < 100MB |
| Startup | cold start time | < 10s |
