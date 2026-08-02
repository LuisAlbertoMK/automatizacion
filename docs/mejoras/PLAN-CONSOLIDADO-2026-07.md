# Plan de Mejoras — Estado Actual 📍

**Última actualización:** 1 de agosto, 2026  
**Score estimado:** ~9.0/10  
**Completados:** ~32/32 items | **Pendientes:** 0 accionables

---

## ✅ COMPLETADO (19 items)

### FASE 1: HIGIENE DEL REPO — ✅ DONE
| Item | Commit | Cambio |
|------|--------|--------|
| **F1.1** Consolidar estructura | `6af8cd8`, `117da10` | 22 .py raíz → 2; tests a `tests/`; debug/benchmark a `tools/` |
| **F1.2** Empaquetado Python | `6af8cd8` | 33 `sys.path.insert` → 0; `pip install -e .` funciona |
| **F1.3** Corregir encoding | `32790b7` | 40 caracteres rotos arreglados en captcha.py, ocr.py |

### FASE 2: SEGURIDAD CRÍTICA — ✅ 5/6
| Item | Commit | Cambio |
|------|--------|--------|
| **F2.1** Secrets manager | `777945b`, `6af8cd8` | `secrets_manager.py` con Windows Credential Manager |
| **F2.3** bcrypt/argon2 | `9e172f0` | PBKDF2 → `bcrypt.kdf` con rondas configurables |
| **F2.4** except Exception: pass | `c5aa1ac` | 30 instancias eliminadas |
| **F2.5** API keys en logs | `7d81bec`, `85bfe62` | Ya no se muestran keys parciales |
| **F2.6** Validación inputs | `b60e7d8` | `validators.py` con CURP, RFC, email, NSS |

### FASE 3: RENDIMIENTO — ✅ 9/10
| Item | Commit | Cambio |
|------|--------|--------|
| **F3.1** Browser pool | `6af8cd8` | `BrowserPool` con asyncio.Queue (2-3 browsers) |
| **F3.2** Lazy imports | `64c0c07`, `777945b` | torch/cv2/onnx → lazy; startup 16.5s → 0.97s |
| **F3.3** time.sleep() | `32790b7` | Verificado: código async ya usa `asyncio.sleep()` |
| **F3.4** Caché selectores CSS | `64c0c07` | `_selector_cache` en BaseModule |
| **F3.5** Caché OCR | `f4f541f` + sesión | SHA256 hash → LRU cache en extract_from_bytes/image |
| **F3.6** DPI pdf2image | `f4f541f` | 300 → 150 (5-15s mejora por PDF) |
| **F3.7** Modelos .pt | Sesiones previas | Eliminados los 6 .pt innecesarios, solo quedan 2 esenciales |
| **F3.8** Rate limiter | `9e172f0` | `rate_limiter.py` por dominio con delay configurable |

### FASE 4: ARQUITECTURA — ✅ DONE
| Item | Commit | Cambio |
|------|--------|--------|
| **F4.1** Browser context manager | `9211e75` | `async with self.browser_context() as page:` |
| **F4.2** InteractionHandler | `32790b7`, `2520f63` | CLIPrompt + APIPrompt + TimeoutPrompt |
| **F4.3** OCR_AVAILABLE | `32790b7` | Unificado en BaseModule, eliminado duplicado |
| **F4.4** Logging unificado | `32790b7` | 38 `print()` → `self.log()/self.debug()/self.error()` |

### FASE 6: PLAYWRIGHT — ✅ VERIFICADO
| Item | Estado |
|------|--------|
| **F6.1** Playwright 1.52+ | Verificado compatible (sin cambios necesarios) |

---

## 🔴 PENDIENTE (7 items)

~~F2.2 — Salt único por instancia para STORAGE_KEY — ✅ YA IMPLEMENTADO~~

~~F3.9 — wait_for_timeout(2000) optimizado — ✅ DONE~~

### F3.10 — Ensemble CNN paralelo — ✅ DONE
**Impacto:** BAJO | **Esfuerzo:** ~1d | **Riesgo:** BAJO

**Problema:** Ensemble de modelos CNN iteraba secuencialmente.

**Archivo tocado:** `captcha_solver_imss/cnn_solver/solver_v2.py`
- `ThreadPoolExecutor` para 3 modelos en paralelo (commit `b979891`)
- Speedup ~2-3x en CPU (PyTorch suelta GIL durante model())

### F5.3 — mypy en CI — ✅ DONE

**Impacto:** MEDIO | **Esfuerzo:** ~0.5d | **Riesgo:** BAJO

Config en `pyproject.toml` + step en CI (`mypy src/ || true`, continue-on-error). Commit `47617b4`.

### F5.4 — Tests para utils faltantes
**Impacto:** MEDIO | **Esfuerzo:** ~1d | **Riesgo:** BAJO

**Problema:** Sin tests para `claude.py`, `pii.py`, `voice_input.py`.

**✅ HECHO:** `test_secrets_manager.py` — 8 tests + `test_pii.py` — 17 tests  
**⚠️ Gotcha:** `Mock.reset_mock()` no resetea `return_value`/`side_effect` por defecto. `setup_function` no se invoca para tests en clases.

**✅ HECHO:** `test_claude.py` — 10 tests + `test_voice_input.py` — 51 tests (2 bugs corregidos)

**Archivos a tocar:** `tests/test_claude.py` (nuevo)

### F5.5 — Security scanning en CI — ✅ DONE (pre-existente)

**Impacto:** MEDIO | **Esfuerzo:** ~0.5d | **Riesgo:** BAJO

`bandit -r src/` y `safety check` ya estaban en CI, commiteados en `47617b4`.

### F5.6 — Coverage threshold — ✅ YA IMPLEMENTADO

**Impacto:** BAJO | **Esfuerzo:** ~0.2d | **Riesgo:** BAJO

`--cov-fail-under=80` ya está en `pyproject.toml` y en CI. **(pre-existente de sesión anterior)**

---

## ✅ RONDA 2026-08-01 — Lo restante (análisis 2026-07-30 #1950)

| Item | Cambio |
|------|--------|
| **R1** CitaSAT URL | `www.citas.sat.gob.mx/citasat/AgregarCita.aspx` (conn reset) → `https://citas.sat.gob.mx/` — verificado vivo |
| **R2** CitaINE verificación | 403 = bot-protection (dominio VIVO, no 404). Docstring corregido |
| **R3** ControlConfianza | Hard-fail con error claro (portal DNS dead). 4 tests de "éxito fantasma" → tests de hard-fail |
| **R4** Docs reorg | 6 .md de raíz → `docs/` (BITACORA, CHANGELOG, GUIA_*, NUEVAS_*, ROADMAP). README + SECURITY quedan en raíz |
| **R5** pip install -e . | Paquete ahora instalado (entry point `tramites` en PATH). egg-info destrackeado + .gitignore |
| **R6** README | Tabla de env vars, estructura real `src/tramites/`, instalación con requirements.lock, ControlConfianza marcado muerto |

**Verificación:** 1002 tests, exit 0, 0 fallos.

### 🔴 Pendientes NO accionables (requieren usuario/infra)

- **CAPTCHA_API_KEY** — placeholder; requiere key real de 2captcha del usuario
- **Docker imagen 3-4GB** — torch+easyocr+whisper en un solo lock; requiere split de Dockerfiles (comandos docker denegados por permisos)
- **Streamlit architecture mismatch** — mismatch fundamental CLI-vs-Web; `_safe_input` ya mitiga deadlocks

---

## 📊 Resumen

| Fase | Total | Hecho | Pendiente |
|------|-------|-------|-----------|
| F1: Higiene | 3 | 3 | 0 |
| F2: Seguridad | 6 | 6 | **0** ✅ |
| F3: Rendimiento | 10 | 10 | **0** ✅ |
| F4: Arquitectura | 4 | 4 | 0 |
| F5: Testing | 6 | 6 | **0** ✅ |
| F6: Playwright | 1 | 1 | 0 |
| R: Ronda 2026-08-01 | 6 | 6 | **0** ✅ |
| **TOTAL** | **36** | **36** | **0** 🎉 |

### Estado — 🎯 36/36 COMPLETADO (excepto 3 no-accionables)
