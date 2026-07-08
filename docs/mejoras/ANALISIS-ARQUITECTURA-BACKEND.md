# Análisis de Arquitectura y Backend

**Proyecto:** agente-tramites-gobmx  
**Fecha:** 2026-07-08  
**Analista:** Señor Arquitecto (subagente especializado)

---

## Stack Detectado

| Capa | Tecnología |
|------|-----------|
| Lenguaje | Python 3.10+ |
| Browser automation | Playwright (Firefox) |
| API REST | FastAPI |
| CLI | argparse |
| UI Web | Streamlit |
| Captcha | 2captcha + FreeCaptcha (EasyOCR + Tesseract) |
| Crypto | Fernet (AES-128-CBC) + PBKDF2 |
| OCR | Tesseract + EasyOCR + CNN ensemble |
| Voz | Whisper (openai) |
| Almacenamiento | JSON encriptado + PBKDF2 hashing |

---

## Hallazgos Críticos (pueden romper)

### 🔴 H1 — Browser Pool: tipo polimórfico que puede corromper el pool

**Archivo:** `src/modules/base.py:77-160`

`launch_browser()` retorna tupla polimórfica según si hay pool:
- Con pool → `(pool, browser, page)` — `p` es `BrowserPool`
- Sin pool → `(p, browser, page)` — `p` es `Playwright`

`close_browser()` usa `p` para DOS cosas distintas sin type-checking:
- `await p.release(browser)` → asume `BrowserPool`
- `await p.__aexit__(None, None, None)` → asume `Playwright`

Si ocurre una excepción entre launch y close, o si los modos se mezclan, se llama `release()` sobre un `Playwright` (AttributeError) o `__aexit__` sobre un `BrowserPool`. El browser queda colgado.

### 🔴 H2 — Browser Pool: sin heartbeat ni detección de browsers caídos

**Archivo:** `src/utils/browser_pool.py`

- Sin heartbeat: si Firefox crashea silenciosamente, el pool no lo detecta
- `acquire()` llama `initialize()` cada vez (innecesario)
- Si `initialize()` falla a medio camino, deja `_initialized=True` con pool parcial
- Sin lock en `self._last_used[browser]` (frágil para migración a procesos)

### 🔴 H3 — API REST expone solo 2 de 14 módulos

**Archivo:** `src/api.py:215-242`

| Endpoint | Expone | Faltan (12 módulos) |
|----------|--------|---------------------|
| POST /curp | CURP | RFC, Acta, Pasaporte, Semanas, Control Confianza, Buró, Círculo, Cita INE, Cita SAT, Antecedentes, Tenencia, Documentos |
| POST /nss | NSS | |
| GET /perfiles | Perfiles | |
| POST/perfiles | Perfiles | |

**86% de la funcionalidad del CLI no disponible via REST.**

### 🔴 H4 — Rate limiting global: `_last_request_time` compartida entre módulos

**Archivo:** `src/modules/base.py:27-37`

Variable global compartida entre todos los módulos. Si CURP hace un request en t=0s y NSS en t=1s, NSS espera 1s adicional aunque sean portales DISTINTOS. Causa head-of-line blocking en concurrencia.

### 🔴 H5 — Resource leak en pool: context no cerrado si launch falla a medio camino

**Archivo:** `src/modules/base.py:137-159`

Si `launch_browser()` falla DESPUÉS de crear el context pero ANTES de asignarlo a `self._context`, el context queda abierto permanentemente. En pool mode hay 2 contexts por browser que nunca se cierran.

### 🔴 H6 — Captcha solver recreado en cada request HTTP

**Archivo:** `src/api.py:176-188`

`_get_solver()` se llama en CADA handler del endpoint. Verifica balance de 2captha en cada request, reimporta módulos. Overhead de ~300-500ms por request.

---

## Deuda Técnica

| ID | Hallazgo | Archivo | Severidad |
|----|----------|---------|-----------|
| T1 | BaseModule es god object con 15+ responsabilidades (browser, DOM, captcha, PDF, OCR, logging, rate limiting) | `base.py` (513 líneas) | 🟡 Alta |
| T2 | Triple dispatch de trámites: Agente class, modo_directo, TramitesOrchestrator — lógica duplicada | `main.py:535-632`, `orchestrator.py` | 🟡 Alta |
| T3 | Logger con PII leak parcial: faltan RFC, teléfonos, direcciones en patrones de sanitización | `logger.py:59-63` | 🟡 Media |
| T4 | Browser Pool ignora `HEADLESS` env var (hardcodeado `True`) | `browser_pool.py:47` | 🟡 Media |
| T5 | Sin caching de resultados — cada consulta paga launch + captcha + scraping completo | Todos los módulos | 🟡 Alta |
| T6 | numpy<2.0 bloquea dependencias modernas (opencv, onnxruntime ya migraron) | `pyproject.toml:23` | 🟡 Baja |
| T7 | Docker build ineficiente: pip install dos veces | `Dockerfile:7-11` | 🟡 Baja |
| T8 | Sin tests de integración para módulos reales | `tests/` | 🟡 Alta |
| T9 | `noqa: E402` dispersos por imports post-load_dotenv | `main.py` (7 instancias) | 🟡 Baja |
| T10 | `orchestrator.py` pasa `use_ocr=True` siempre sin detectar disponibilidad | `orchestrator.py:99` | 🟡 Media |

---

## Recomendaciones Prioritarias

### 🔴 Prioridad Alta

| ID | Cambio | Archivos | Esfuerzo |
|----|--------|----------|----------|
| A1 | Refactorizar `launch_browser()` para retornar objeto `BrowserResources` con tipo único | `base.py:77-160` | 1 día |
| A2 | Agregar heartbeat a BrowserPool: verificar `browser.is_connected()` | `browser_pool.py:64-94` | 1 día |
| A3 | Singleton del captcha solver en API (inicializar al startup) | `api.py:176-188` | 0.5 día |
| A4 | Cache LRU de resultados con TTL configurable | Módulos de trámite | 1 día |
| A5 | Rate limiting por portal (no global) con dict keyeado por dominio | `base.py:27-37` | 0.5 día |

### 🟡 Prioridad Media

| ID | Cambio |
|----|--------|
| B1 | Agregar los 12 endpoints faltantes a api.py |
| B2 | Unificar dispatch: eliminar `modo_directo`, usar TramitesOrchestrator siempre |
| B3 | Extraer BrowserService, CaptchaService, PdfService de BaseModule |
| B4 | Hacer BrowserPool respete HEADLESS env var |
| B5 | Ampliar PII sanitization: RFC, teléfonos, direcciones |
| B6 | Tests de integración con mock de Playwright |

---

## Fortalezas a Preservar

- ✅ Jerarquía de excepciones sólida (17 clases, 3 niveles de herencia)
- ✅ Logger con PII sanitization + TramiteMetrics persistido en JSONL
- ✅ Template de módulo claro (`template.py`) con TODO estratégicos
- ✅ Pool de browsers como singleton (concepto correcto, bugs corregibles)
- ✅ Anti-detección en browser (User-Agent real, locale es-MX, navigator.webdriver)
- ✅ Almacenamiento encriptado con Fernet + PBKDF2 (600k iteraciones)
- ✅ Rate limits configurables por endpoint en API
- ✅ 14 módulos de trámite con interfaz uniforme
- ✅ Soporte multimodal (voz, imagen, texto)
