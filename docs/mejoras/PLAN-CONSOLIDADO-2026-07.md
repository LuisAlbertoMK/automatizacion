# Plan de Mejoras — Estado Actual 📍

**Última actualización:** 8 de julio, 2026  
**Score estimado:** ~8.5/10  
**Completados:** ~19/26 items | **Pendientes:** 7 items

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

### FASE 3: RENDIMIENTO — ✅ 8/10
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

### F2.2 — Salt único por instancia para STORAGE_KEY
**Impacto:** CRÍTICO | **Esfuerzo:** ~1d | **Riesgo:** BAJO

**Problema:** Salt hardcodeado `b"fernet-key-salt"` en `storage.py`. Dos instancias con misma STORAGE_KEY generan clave Fernet idéntica.

**Archivos a tocar:** `src/utils/storage.py`
- Generar salt aleatorio al primer uso
- Guardar en `data/` persistente
- `storage_migrate_salt()` ya existe para migración

### F3.9 — wait_for_timeout(2000) optimizado
**Impacto:** MEDIO | **Esfuerzo:** ~1d | **Riesgo:** MEDIO

**Problema:** `await page.wait_for_timeout(2000)` en `base.py:235,243` espera 2s fijos post-navegación.

**Archivos a tocar:** `src/tramites/base.py`
- Reemplazar por `wait_for_selector()` del primer elemento clave
- O timeout dinámico según portal

### F3.10 — Ensemble CNN paralelo
**Impacto:** BAJO | **Esfuerzo:** ~1d | **Riesgo:** BAJO

**Problema:** Ensemble de modelos CNN itera secuencialmente.

**Archivos a tocar:** `captcha_solver_imss/cnn_solver/solver_v2.py`
- Usar `ThreadPoolExecutor` para 3 modelos en paralelo

### F5.3 — mypy en CI
**Impacto:** MEDIO | **Esfuerzo:** ~0.5d | **Riesgo:** BAJO

**Problema:** Type hints existen pero no se validan.

**Archivos a tocar:** `mypy.ini` (nuevo), `.github/workflows/`
- Config mypy básica
- Agregar a CI

### F5.4 — Tests para utils faltantes
**Impacto:** MEDIO | **Esfuerzo:** ~1d | **Riesgo:** BAJO

**Problema:** Sin tests para `claude.py`, `pii.py`, `voice_input.py`, `secrets_manager.py`.

**Archivos a tocar:** `tests/test_claude.py`, `tests/test_pii.py`, `tests/test_secrets.py` (nuevos)

### F5.5 — Security scanning en CI
**Impacto:** MEDIO | **Esfuerzo:** ~0.5d | **Riesgo:** BAJO

**Problema:** Sin detección automática de secrets/vulnerabilidades.

**Archivos a tocar:** `.github/workflows/`, `pyproject.toml`
- `bandit -r src/`
- `safety check`

### F5.6 — Coverage threshold
**Impacto:** BAJO | **Esfuerzo:** ~0.2d | **Riesgo:** BAJO

**Problema:** Coverage se reporta pero no hay mínimo.

**Archivos a tocar:** `pyproject.toml`
- `--cov-fail-under=80` en pytest

---

## 📊 Resumen

| Fase | Total | Hecho | Pendiente |
|------|-------|-------|-----------|
| F1: Higiene | 3 | 3 | 0 |
| F2: Seguridad | 6 | 5 | **1** (F2.2 salt único) |
| F3: Rendimiento | 10 | 8 | **2** (F3.9 timeout, F3.10 ensemble) |
| F4: Arquitectura | 4 | 4 | 0 |
| F5: Testing | 6 | 0 | **4** (F5.3-F5.6) |
| F6: Playwright | 1 | 1 | 0 |
| **TOTAL** | **30** | **21** | **7** |

### Prioridad sugerida
1. 🥇 **F2.2** — Salt único (seguridad crítica, ~1d)
2. 🥇 **F3.9** — wait_for_timeout optimizado (~1d)
3. 🥇 **F5.3-F5.6** — CI/testing (~2d total)
4. 🥈 **F3.10** — Ensemble paralelo (~1d)
