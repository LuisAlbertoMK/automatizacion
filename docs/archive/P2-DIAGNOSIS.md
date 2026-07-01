# P2: DIAGNOSE — agente-tramites-gobmx

**Date**: 2026-07-01
**Subagents**: 3 (Quality, Security, Performance)

---

## 1. Quality Diagnosis

### Test Coverage
| Area | Coverage | Assessment |
|------|----------|------------|
| Core utilities (captcha, exceptions, logger, storage) | 90-100% | ✅ Excelente |
| base.py | 92% | ✅ Bueno |
| main.py / orchestrator.py | 70-71% | ⚠️ Aceptable |
| **Tramite modules** (curp, nss, tenencia, etc.) | **11-19%** | ❌ **CRÍTICO** |
| utils (free_captcha, multimodal, voice, claude) | 15-29% | ❌ Bajo |

### Code Duplication
- **~1000 líneas duplicadas** entre los 13 módulos de trámite (try/except/finally boilerplate)
- **buro.py y circulo.py ~95% idénticos**
- 14-branch `if/elif` en `orchestrator.py:134` y 16-branch en `main.py:472`

### Error Handling
- Jerarquía de excepciones excelente (15 clases)
- ~15 `except Exception: pass/continue` en toda la base
- `print()` inconsistente vs `self.log()` entre módulos

### Ruff
- **Zero violations** — pero config demasiado permisiva (solo E/F/W/I)

### Key Findings
| # | Severidad | Archivo | Descripción |
|---|-----------|---------|-------------|
| Q1 | **CRITICAL** | modules/curp.py, nss.py, tenencia.py, etc. (13 archivos) | Sin unit tests — coverage 11-19% |
| Q2 | **HIGH** | modules/rfc.py:42, acta_nacimiento.py:35, etc. (9 archivos) | Boilerplate try/except/finally duplicado (~180 líneas) |
| Q3 | **HIGH** | modules/buro.py / circulo.py | ~95% idénticos |
| Q4 | **MEDIUM** | modules/pasaporte.py:67 | `_run()` = 127 líneas (viola SRP) |
| Q5 | **MEDIUM** | modules/nss.py:388 | `_obtener_nss()` = 96 líneas, 5 niveles de anidación |
| Q6 | **MEDIUM** | orchestrator.py:134, main.py:472 | Cadenas if/elif de 14-16 ramas (deberían ser diccionarios) |
| Q7 | **MEDIUM** | modules/rfc.py:65, +8 archivos | Falta type hint `page: Page` en _run() |
| Q8 | **MEDIUM** | modules/curp.py, tenencia.py, nss.py | `print()` usado en lugar de `self.log()` estructurado |
| Q9 | **MEDIUM** | modules/curp.py:277, antecedentes.py:241, nss.py:302,472 | Bare `except Exception: continue/pass` |
| Q10 | **LOW** | modules/template.py | Código muerto (29 líneas, 0% coverage) |

---

## 2. Security Diagnosis

### Findings by Severity

| # | Severidad | Archivo:Linea | Descripción |
|---|-----------|---------------|-------------|
| S1 | **HIGH** | modules/antecedentes.py:126 | Contraseña generada impresa en texto plano a stdout |
| S2 | **HIGH** | utils/storage.py:39-40 | Sin key stretching en STORAGE_KEY (solo SHA-256 simple) |
| S3 | **MEDIUM** | main.py:214,262; orchestrator.py:259; ocr.py:292; voice_input.py:171 | CURP, email, NSS impresos a stdout sin sanitizar |
| S4 | **MEDIUM** | utils/logger.py:57-81 | Logger no sanitiza PII antes de escribir a archivo |
| S5 | **MEDIUM** | modules/base.py:79 | Firefox lanzado sin argumentos de sandbox |
| S6 | **MEDIUM** | api.py:136-211 | Sin autenticación en ningún endpoint |
| S7 | **MEDIUM** | api.py:92-93 | Swagger/ReDoc expuestos en producción |
| S8 | **MEDIUM** | api.py:88-99 | Sin CORS middleware |
| S9 | **MEDIUM** | api.py:190-195 | Lista de perfiles pública (sin auth) |
| S10 | **MEDIUM** | docker-compose.yml:32,57 | API y UI sirven HTTP plano en 0.0.0.0 |
| S11 | **MEDIUM** | free_captcha.py:227, voice_input.py:91 | Archivos temporales con `delete=False` pueden persistir |
| S12 | **MEDIUM** | docker-compose.yml:8-9,27-28,46-47 | Todos los secretos en un solo archivo plano montado en contenedores |
| S13 | **MEDIUM** | requirements.txt, pyproject.toml:12-24 | Sin pinning de versiones (solo `>=`) |
| S14 | **LOW** | modules/base.py:90-92 | Anti-detección solo enmascara `navigator.webdriver` |
| S15 | **LOW** | modules/curp.py:105, nss.py:105, antecedentes.py:83 | Screenshots con nombres predecibles en raíz del proyecto |

---

## 3. Performance Diagnosis

### Findings by Severity

| # | Severidad | Archivo | Descripción |
|---|-----------|---------|-------------|
| P1 | **CRITICAL** | base.py:76 | Sin reuso de browser — Firefox fresh por cada trámite (~800ms-2s overhead) |
| P2 | **CRITICAL** | utils/captcha.py:262 | Polling síncrono con `time.sleep(5)` bloquea event loop hasta 120s |
| P3 | **CRITICAL** | Dockerfile | Sin multi-stage build — imagen estimada ~3-4GB |
| P4 | **CRITICAL** | Dockerfile:7,17 | Firefox instalado 2 veces (ESR + Playwright) |
| P5 | **CRITICAL** | nss.py:457 | `wait_for_imss_email()` bloquea event loop hasta 180s sin `run_in_executor` |
| P6 | **HIGH** | captcha_solver_imss/solver.py:619 | EasyOCR Reader (~1.5-2GB RAM) nunca se descarga |
| P7 | **HIGH** | captcha_solver_imss/cnn_solver/solver_v2.py:117 | Ensemble carga hasta 3 modelos PyTorch simultáneamente |
| P8 | **HIGH** | src/main.py:58-77 | Imports top-level cargan Playwright + Torch + EasyOCR al inicio (~3-8s cold start) |
| P9 | **HIGH** | captcha_solver_imss/solver.py:78 | Modelos .pt cargados eager en construcción de solver |
| P10 | **MEDIUM** | base.py:111 | `asyncio.sleep(2)` fijo tras cada navegación |
| P11 | **MEDIUM** | base.py:30 | `REQUEST_DELAY` fijo de 2s — no adaptativo |
| P12 | **MEDIUM** | utils/captcha.py:31 | `_verify_balance()` llamado en cada instanciación (~500ms-1s) |
| P13 | **MEDIUM** | utils/ocr.py:103-107 | PDF a imagen sin caché (5-15s por documento) |
| P14 | **MEDIUM** | utils/ocr.py:42, free_captcha.py:36, solver.py:643 | Tesseract verificado 3 veces al inicio |

---

## Summary

| Área | Fortalezas | Debilidades Críticas |
|------|------------|---------------------|
| **Calidad** | Tests core, jerarquía excepciones, ruff clean | Sin tests en módulos de trámite, ~1000 líneas duplicadas |
| **Seguridad** | Encriptación Fernet, PBKDF2 en campos sensibles, .dockerignore | Passwords en stdout, sin key stretching, API sin auth |
| **Performance** | CNN solver rápido (2-50ms), lazy loading parcial | Sin pool de browsers, EasyOCR 2GB RAM, Docker 3-4GB |

---

## Gate: All 3+ reports complete ✅ → Proceeding to P3
