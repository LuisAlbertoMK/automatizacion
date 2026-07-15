# 🔍 Análisis Multi-Agente — automatizacion (2026-07-14)

**Proyecto:** agente-tramites-gobmx  
**Stack:** Python 3.10+ · Playwright · Streamlit · FastAPI · Docker  
**Especialistas:** Security · Performance · UX · Infrastructure · Architecture · DX · SEO  
**Modo:** Análisis-only — sin cambios de código

---

## 📋 Executive Summary

El proyecto tiene una **base técnica sólida** — módulos bien estructurados, jerarquía de excepciones, suite de tests extensa, y Docker multi-stage correcto. Sin embargo, creció orgánicamente sin consolidación, acumulando deuda técnica significativa.

| Dimensión | Riesgo | Hallazgos Críticos |
|-----------|--------|-------------------|
| 🔒 Security | **HIGH** | Auth bypass por defecto, PII expuesto en Docker inspect |
| ⚡ Performance | **MEDIUM** | Sync en async context, waits hardcodeados, Whisper eager |
| 🎨 UX | **HIGH** | Sin validación en UI, sin onboarding, errores genéricos |
| 🏗️ Infrastructure | **HIGH** | Sin CI/CD, sin restart policies, sin log rotation |
| 🧱 Architecture | **HIGH** | 3 entry points duplicados, BaseModule god class, shims innecesarios |
| 🛠️ DX | **MEDIUM** | Documentación contradictoria, mypy deshabilitado, sin CONTRIBUTING |
| 🔍 SEO | **HIGH** | Sin meta tags, sin structured data, API docs deshabilitadas |

**Prioridad Inmediata (Semana 1):**
1. Eliminar `src/modules/` shim + actualizar imports
2. Requerir API_KEY en producción, añadir auth a Streamlit
3. Añadir `.github/workflows/ci.yml` básico
4. Fix: `hmac.compare_digest` para API key
5. Validación real en Streamlit (usar validators.py existente)

---

## 🔒 1. Security — Riesgo: HIGH

### Hallazgos Críticos

**[SEC-01] Auth Bypass por Defecto** (HIGH)
- `src/api.py:78-79` — Cuando `API_KEY` está vacío, auth se desactiva silenciosamente
- Docker-compose expone `0.0.0.0:8000` → API abierta al mundo
- **Fix:** En producción, rechazar startup si API_KEY falta

**[SEC-02] Streamlit Sin Autenticación** (HIGH)
- `docker-compose.yml:38` — Streamlit en `0.0.0.0:8501` sin auth
- Cualquiera con acceso puede consultar CURPs/NSS
- **Fix:** Reverse proxy (nginx/caddy) con auth, o OAuth2

**[SEC-03] Secrets en Docker inspect** (HIGH)
- `docker-compose.yml:8-9` — `env_file: config.env` visible via `docker inspect`
- **Fix:** Docker secrets o runtime injection, no `env_file`

**[SEC-04] Timing Attack en API Key** (MEDIUM)
- `src/api.py:82` — Comparación con `!=` (short-circuit)
- **Fix:** `hmac.compare_digest(key, API_KEY)` — una línea

**[SEC-05] Email Sin Validación en NSS API** (MEDIUM)
- `src/api.py:98-101` — `NssRequest.correo` sin `field_validator`
- **Fix:** Usar `validar_email` de validators.py

**[SEC-06] Rate Limiting Deshabilitado Silenciosamente** (MEDIUM)
- `src/api.py:55-62` — Si `slowapi` falta, limiter es noop
- **Fix:** Hard dependency en producción

**[SEC-07] Playwright Sin Sandbox** (MEDIUM)
- `src/tramites/base.py:177-178` — `PLAYWRIGHT_NO_SANDBOX` configurable
- **Fix:** Default sandboxed, documentar excepciones

### Lo Que Está Bien
- `secrets_manager.py` con Windows Credential Manager
- Fernet encryption con bcrypt KDF (600k rounds)
- Non-root Docker user (appuser:1000)
- `.gitignore` excluye `config.env`
- Docs deshabilitadas en producción

---

## ⚡ 2. Performance — Riesgo: MEDIUM

### Hallazgos

**[PERF-01] Blocking I/O en Async Context** (HIGH)
- `src/utils/captcha.py:80,119,165` — `requests` sync + `time.sleep()` polling
- `base.py:389` llama versión sync en vez de `_async`
- **Impacto:** Cada CAPTCHA bloquea thread pool 15-120s
- **Fix:** Usar `solve_image_async` nativo

**[PERF-02] Browser Pool Cleanup Drain** (HIGH)
- `src/utils/browser_pool.py:67-90` — Drena toda la cola durante cleanup
- `acquire()` se bloquea durante la limpieza
- **Fix:** Check lazy en `acquire()`, o separate idle set

**[PERF-03] Waits Hardcodeados** (MEDIUM)
- `base.py:259` — 500ms fijo post-networkidle
- `fill_field` +300ms, `click_first` +1s
- **Impacto:** CURP (~6 interacciones) = 8-10s de puro wait
- **Fix:** Event-based waits (`wait_for_selector`)

**[PERF-04] Whisper Eager Load** (MEDIUM)
- `voice_input.py:66` — Modelo se carga en `__init__` aunque nunca se use
- **Impacto:** +3-10s startup, 150MB RAM permanente
- **Fix:** Lazy load con `@cached_property`

**[PERF-05] Rate Limiter Global Mutable** (MEDIUM)
- `base.py:79-89` — `_last_request_time` sin thread safety
- **Fix:** Usar `rate_limiter.limiter` existente

**[PERF-06] OCR Preprocessing Redundante** (LOW)
- `ocr.py:157-188` — PIL preprocessing en cada imagen
- **Fix:** Parallelizar PDFs, simplificar para CAPTCHAs pequeños

---

## 🎨 3. UX — Riesgo: HIGH

### Hallazgos Críticos

**[UX-01] Sin Validación Real en UI** (HIGH)
- `app.py:102-104` — Solo check `len(curp) != 18`, NO usa `validar_curp()`
- `app.py:119-122` — Email: `@ not in correo` en vez de `validar_email()`
- **Impacto:** CURPs malformados esperan 16s para fallar en RENAPO
- **Fix:** Llamar funciones existentes de validators.py

**[UX-02] Sin Onboarding** (HIGH)
- Primera vez: Dashboard directo, warning críptico "Sin 2captcha"
- **Fix:** Wizard de primera vez, explicar configuración

**[UX-03] Errores Genéricos Sin Recovery** (HIGH)
- `app.py:113` — `st.error(f"Error: {e}")` para todo
- Sin retry, sin diferenciar tipos de error
- **Fix:** Categorizar excepciones, botón retry

**[UX-04] Eliminación de Perfil Sin Confirmación** (MEDIUM)
- `app.py:148-150` — Un click elimina perfil permanentemente
- **Fix:** `st.dialog` o flujo de dos pasos

**[UX-05] Sin Indicadores de Progreso** (MEDIUM)
- Solo `st.spinner` para operaciones de 30-60s
- **Fix:** `st.progress()` con fases estimadas

**[UX-06] Dashboard Con Métricas de Dev** (LOW)
- Muestra "Producción/Escrito/Planificado" — meaningless para usuarios
- **Fix:** Métricas user-centric: última consulta, perfiles guardados

---

## 🏗️ 4. Infrastructure — Riesgo: HIGH

### Hallazgos

**[INFRA-01] Sin CI/CD** (HIGH)
- `.github/` no existe. Zero automatización.
- **Fix:** `.github/workflows/ci.yml` — lint, test, build, push

**[INFRA-02] Sin Restart Policies** (MEDIUM)
- Docker-compose sin `restart:`, sin resource limits
- Firefox + ML = 2-4GB RAM sin protección
- **Fix:** `restart: unless-stopped` + `mem_limit: 4G`

**[INFRA-03] Health Check Incompleto** (HIGH)
- No verifica que Firefox funcione, solo imports
- **Fix:** Test de browser en health check

**[INFRA-04] Sin Log Rotation** (MEDIUM)
- `tramites.log` crece indefinidamente
- **Fix:** `RotatingFileHandler` 10MB × 5 backups

**[INFRA-05] Imagen Pesada** (MEDIUM)
- ML deps (whisper, opencv, onnx) = 3-5GB+
- **Fix:** Profiles condicionales, requirements-prod.txt

**[INFRA-06] Secrets en Plaintext** (MEDIUM)
- `env_file: config.env` visible via docker inspect
- **Fix:** Docker secrets o runtime injection

---

## 🧱 5. Architecture — Riesgo: HIGH

### Hallazgos

**[ARCH-01] Tres Entry Points Duplicados** (HIGH)
- `main.py` (Agente class, 364 líneas), `orchestrator.py` (482 líneas), `api.py` (282 líneas)
- Cada uno reimplementa instantiate, input, error handling
- **Fix:** Consolidar a UN orchestrator usado por todos

**[ARCH-02] `src/modules/` Shim Layer** (MEDIUM)
- 18+ archivos shim que re-exportan de `src/tramites/`
- Confusión de imports, doble namespace
- **Fix:** Eliminar `src/modules/`, actualizar registry

**[ARCH-03] BaseModule God Class** (HIGH)
- 596 líneas, 8+ responsabilidades
- Browser lifecycle, field filling, CAPTCHA, PDF, logging, regex parsing
- **Fix:** Extraer BrowserManager, SelectorResolver, CaptchaPipeline

**[ARCH-04] Input Collection Duplication** (HIGH)
- 14 `_ejecutar_*` métodos casi idénticos en orchestrator + Agente
- **Fix:** Schema declarativo por trámite + `_collect_inputs(schema)` genérico

**[ARCH-05] Exception Hierarchy Underutilized** (MEDIUM)
- Jerarquía bien diseñada pero callers catch `Exception` genérico
- API retorna 500 para todo
- **Fix:** Mapear ModuleError → HTTP codes específicos

**[ARCH-06] No DI / Service Registry** (MEDIUM)
- CaptchaSolver/MailReader inicializados independientemente en 3 lugares
- **Fix:** ServiceRegistry singleton con constructor injection

---

## 🛠️ 6. Developer Experience — Riesgo: MEDIUM

### Hallazgos

**[DX-01] Documentación Contradictoria** (HIGH)
- README dice Firefox, GUIA_COMPLETA dice Chromium
- 8+ docs con info inconsistente
- **Fix:** CONTRIBUTING.md como single source of truth

**[DX-02] mypy Deshabilitado** (MEDIUM)
- Config: `check_untyped_defs = false`, `disallow_untyped_defs = false`
- CI: `mypy src/ || true`
- **Fix:** Enable `check_untyped_defs`, remover `|| true`

**[DX-03] requirements.txt vs pyproject.toml** (MEDIUM)
- requirements.txt incluye TODO (whisper, opencv, onnx)
- pyproject.toml tiene optional-dependencies limpias
- **Fix:** Eliminar requirements.txt, usar `pip install -e ".[test]"`

**[DX-04] Sin Setup Script** (MEDIUM)
- No Makefile, no justfile, no setup automation
- **Fix:** Makefile con `setup`, `test`, `lint`, `run`

**[DX-05] Security Scans Swallowed** (MEDIUM)
- `bandit -r src/ || true` — nunca falla el build
- **Fix:** `bandit -r src/ -ll` (fail on HIGH)

**[DX-06] conftest Usa API Interna de pytest** (LOW)
- `_pytest.monkeypatch.MonkeyPatch()` en vez de fixture
- **Fix:** Refactorizar a monkeypatch fixture estándar

---

## 🔍 7. SEO & Web Presence — Riesgo: HIGH

### Hallazgos

**[SEO-01] Sin Meta Tags** (HIGH)
- `app.py:35-40` — Solo `page_title` y `page_icon`
- Sin OG tags, sin Twitter Cards, sin description
- **Fix:** Inyectar meta via `st.markdown(unsafe_allow_html=True)`

**[SEO-02] API Docs Deshabilitadas** (HIGH)
- `api.py:125-126` — `docs_url=None` en producción
- **Fix:** Mantener `/docs` con auth, o generar `openapi.json` estático

**[SEO-03] Sin Structured Data** (MEDIUM)
- Zero Schema.org markup
- **Fix:** JSON-LD `WebApplication` + `WebAPI`

**[SEO-04] Sin Badges ni Topics** (MEDIUM)
- README sin badges, repo sin topic tags
- **Fix:** Badges + topics: `curp`, `nss`, `tramites-gobierno`, `mexico`

**[SEO-05] Sin og:image ni Favicon** (MEDIUM)
- Emoji genérico como page_icon
- **Fix:** Brand image 512x512, favicon custom

---

## 🎯 Risk Matrix

| Hallazgo | Probabilidad | Impacto | Prioridad |
|----------|-------------|---------|-----------|
| SEC-01 Auth bypass | Alta | Crítico | **P0** |
| SEC-02 Streamlit sin auth | Alta | Crítico | **P0** |
| ARCH-01 Entry points duplicados | Alta | Alto | **P1** |
| ARCH-03 BaseModule god class | Alta | Alto | **P1** |
| INFRA-01 Sin CI/CD | Alta | Alto | **P1** |
| UX-01 Sin validación en UI | Alta | Medio | **P1** |
| PERF-01 Blocking sync en async | Media | Alto | **P2** |
| ARCH-04 Input duplication | Alta | Medio | **P2** |
| DX-01 Docs contradictorias | Alta | Medio | **P2** |
| SEC-04 Timing attack | Media | Medio | **P2** |
| PERF-03 Waits hardcodeados | Alta | Medio | **P2** |
| INFRA-03 Health check incompleto | Media | Alto | **P2** |

---

## 🚀 Recomendaciones — Plan de Acción

### Semana 1 (Quick Wins — Bajo Riesgo)
1. **Eliminar `src/modules/` shim** + actualizar imports (~20 archivos)
2. **Fix API key auth:** `hmac.compare_digest` + required in prod
3. **Validación en Streamlit:** Llamar `validar_curp()` y `validar_email()`
4. **Añadir CI básico:** lint (ruff) + test (pytest) en GitHub Actions
5. **Confirmación al eliminar perfil**

### Semana 2 (Arquitectura — Alto Impacto)
6. **Consolidar entry points:** Agente delega a TramitesOrchestrator
7. **Schema declarativo de inputs:** Eliminar duplicación en orchestrator
8. **Extraer componentes de BaseModule:** BrowserManager, CaptchaPipeline
9. **Mapeo de excepciones → HTTP codes** en API

### Semana 3 (Infra & DX)
10. **Restart policies + resource limits** en docker-compose
11. **Log rotation** con RotatingFileHandler
12. **Makefile** con setup, test, lint
13. **CONTRIBUTING.md** como single source of truth
14. **Habilitar mypy** con `check_untyped_defs`

### Semana 4 (Polish)
15. **Meta tags + structured data** en Streamlit
16. **Lazy load de Whisper** para performance
17. **Event-based waits** en Playwright (reemplazar fixed sleeps)
18. **Browser pool cleanup fix**

---

## 📊 Consenso entre Especialistas

**Todos coinciden en:**
- El shim `src/modules/` es innecesario y confuso
- La autenticación es el riesgo #1
- Los 3 entry points son insostenibles
- Falta CI/CD básico

**Divergencias:**
- Security vs DX: Priorizar auth (Security) vs consolidar docs (DX) → **Auth primero**
- Performance vs Architecture: ¿Fix waits (Performance) o refactor BaseModule (Architecture)? → **Refactor primero, waits quedan resueltos**
- Infra vs DX: ¿CI/CD o setup script? → **CI/CD es más urgente**

---

*Análisis generado por 6 especialistas en paralelo · 2026-07-14*
*Próxima ejecución sugerida: después de implementar los Quick Wins de la Semana 1*
