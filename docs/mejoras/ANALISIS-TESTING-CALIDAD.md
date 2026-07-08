# Análisis de Testing y Calidad

**Proyecto:** agente-tramites-gobmx  
**Fecha:** 2026-07-08  
**Analista:** Señor Arquitecto (subagente especializado)

---

## Estadísticas Base

| Métrica | Valor |
|---------|-------|
| Líneas fuente (`src/`) | ~6,700 |
| Líneas de test (`tests/`) | ~3,475 |
| Ratio test:src | 0.52 |
| Archivos de test | 18 (17 scripts + conftest) |
| Tests totales | ~450+ |
| GitHub Actions | ✅ Existe (ci.yml) |
| Coverage report | ❌ Nunca ejecutado |
| Mypy | Cache presente, sin configuración |
| Ruff | ✅ Configurado (E, F, W, I) |

---

## Gaps de Cobertura — Código NO testeado

### Archivos con CERO cobertura

| Archivo | Líneas | Riesgo | Razón |
|---------|--------|--------|-------|
| `src/utils/voice_input.py` | 297 | 🔴 Crítico | Whisper + micrófono; interacción hardware |
| `src/utils/multimodal_input.py` | 270 | 🔴 Crítico | Orquestación texto/voz/imagen |
| `src/modules/documentos/cv.py` | 268 | 🔴 Crítico | Generación CV con Claude + python-docx |
| `src/modules/documentos/escrito.py` | 222 | 🔴 Crítico | Documentos legales con IA |
| `src/utils/free_captcha.py` | 237 | 🔴 Crítico | Ruta default de CAPTCHA sin 2captcha |
| `src/utils/browser_pool.py` | 132 | 🟡 Alto | Singleton + Queue + cleanup async |
| `src/utils/secrets_manager.py` | 125 | 🟡 Alto | Gestión de secretos |
| `src/utils/claude.py` | 75 | 🟡 Alto | Llamadas Anthropic Claude API |
| `src/utils/pii.py` | 43 | 🟡 Medio | Sanitización datos sensibles |

### Módulos con cobertura SOLO del entry point

Los tests solo verifican que `consultar()` retorna lo que `_run()` devuelve. **La lógica real de navegación Playwright nunca se testea:**

- `nss.py` (416 líneas) — solo 3 tests
- `curp.py` (303 líneas) — solo 3 tests
- `base.py` (513 líneas) — branches de pool no testeados
- `captcha.py` — paths de balance cache no testeados

---

## Calidad de Tests Existentes

### Fortalezas

- ✅ Nombres descriptivos
- ✅ Organización por clases
- ✅ Fixtures bien usados
- ✅ Parametrización en exceptions y main
- ✅ Async testing con AsyncMock
- ✅ Verificación de jerarquía de excepciones
- ✅ Edge cases: timeout, red caída, CAPCHA_NOT_READY (typo real), datos corruptos

### Debilidades

| Problema | Ejemplo |
|----------|---------|
| Sobre-mockeo | test_base.py mockea page, locator, requests, solver, os.getenv simultáneamente |
| Poco assertions por test | test_small_modules.py: 4 assertions para 13 tests (0.3/test) |
| Sin tests de integración | Cero tests con browser real o HTTP real |
| Tests de módulos homogéneos | Todos mockean _run, no testean lógica específica |
| Sin smoke tests | No hay test end-to-end del sistema |
| Sin performance tests | No hay benchmarks en CI |
| Sin regression visual | No hay snapshot testing para HTML de portales |
| Cobertura de tipos 0% | Sin mypy checks |

---

## Infraestructura de Testing

### Configuración pytest (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-q --tb=short"
```

**Problemas:**
- ❌ Sin `--strict-markers`
- ❌ Sin `--cov` en addopts
- ❌ Sin `--timeout` — tests colgados cuelgan el suite
- ❌ Sin `-n auto` (pytest-xdist)
- ❌ Sin marcadores registrados

### Coverage (nunca ejecutado)

```toml
[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/__pycache__/*"]
```

- ❌ **Nunca se ejecutó** — no hay `.coverage`, no hay `coverage_html/`
- ❌ Sin `fail_under`
- ❌ Omite ramas condicionales críticas (`if FREE_SOLVER_AVAILABLE`, etc.)
- ❌ Sin `--branch` coverage

### CI/CD (GitHub Actions — ci.yml)

- ✅ Matriz multi-versión Python (3.11, 3.12, 3.13)
- ✅ Ruff linting + compileall
- ✅ pytest con coverage + upload Codecov
- ✅ Docker build en master
- ✅ Uso de `uv` para instalación rápida

**Problemas:**
- 🔴 **Sin deploy automático** — ni registry, ni entorno
- 🔴 **Secrets hardcodeados**: `CAPTCHA_API_KEY: test`, `STORAGE_KEY: test_key_for_ci`
- 🔴 **Sin security scanning** (bandit, safety, trivy)
- 🔴 **Sin type checking** (mypy no se ejecuta)
- 🔴 **Sin tests de integración**
- 🟡 Docker tag siempre `:latest` (sin SHA, sin semver)

---

## Recomendaciones Priorizadas

### 🔴 Crítico

| # | Acción | Justificación |
|---|--------|---------------|
| 1 | Ejecutar `pytest --cov=src --cov-report=html` con `fail_under=60` | Sin métrica de cobertura estás ciego |
| 2 | Testear `free_captcha.py` (237 líneas, ruta default de CAPTCHA) | Cobertura 0% en pipeline crítico |
| 3 | Testear `browser_pool.py` (132 líneas) | Singleton + Queue async sin test |
| 4 | Configurar mypy con `strict = true` | Type hints ya existen, falta verificación |
| 5 | Agregar security scanning a CI (bandit + safety) | Sin escaneo de CVEs |

### 🟡 Alta

| # | Acción |
|---|--------|
| 6 | Testear voice_input.py, multimodal_input.py (570 líneas sin cobertura) |
| 7 | Testear secrets_manager.py (seguridad) |
| 8 | Agregar ruff rules: B, SIM, ARG, RUF |
| 9 | Tests de integración con Playwright (un browser real, un portal) |
| 10 | Smoke test de importación de todos los módulos |

### 🟢 Media

| # | Acción |
|---|--------|
| 11 | Cobertura de branches (`coverage run --branch`) |
| 12 | Pre-commit hooks automatizados |
| 13 | pytest-timeout para evitar suites colgadas |
| 14 | Snapshot testing para HTML de portales |
| 15 | Cobertura de `modo_directo` (solo 4 de 12 trámites testeados) |
