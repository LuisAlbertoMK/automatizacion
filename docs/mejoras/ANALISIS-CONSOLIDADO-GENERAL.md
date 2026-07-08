# 🔬 Análisis Consolidado General — agente-tramites-gobmx

**Fecha:** 2026-07-08  
**Score actual:** 8.0/10  
**Versión:** 1.0.0  
**Analista:** Señor Arquitecto (6 subagentes + síntesis)

---

## Resumen Ejecutivo

El proyecto es un **agente de automatización de trámites gubernamentales mexicanos** con 14 módulos funcionales, UI web (Streamlit), API REST (FastAPI), CLI, y soporte multimodal (texto/voz/imagen).

**Fortaleza principal:** Base técnica sólida — jerarquía de excepciones, encriptación Fernet, sanitización PII, anti-detección browser, pool de browsers, 399 tests.

**Debilidad principal:** Creció de CLI a API + Web sin una refactorización intermedia. El `BaseModule` es un god object, el browser pool tiene bugs de resource leak, y la UI es un MVP funcional.

---

## Mapa de Hallazgos por Área

| Área | Score estimado | Hallazgos críticos | Hallazgos totales |
|------|---------------|-------------------|-------------------|
| 🏗️ Arquitectura | 7.5/10 | 6 | 16 |
| 🔐 Seguridad | 7.0/10 | 4 | 10 |
| 🎨 UI/UX | 4.6/10 | 6 | 17 |
| 🧪 Testing | 6.0/10 | 5 | 15 |
| ⚡ Performance | 5.5/10 | 5 | 15 |
| 🚀 DevOps | 7.0/10 | 5 | 20+ |

---

## Prioridades — Plan de Acción por Semanas

### 🔴 Semana 1: Correcciones Críticas (no negociables)

| # | Área | Acción | Archivos | Esfuerzo |
|---|------|--------|----------|----------|
| 1 | 🔐 Seguridad | Eliminar `--no-sandbox` de Playwright o hacerlo condicional | `base.py:116` | 15 min |
| 2 | 🔐 Seguridad | CORS restrictivo en producción (nunca `*`) | `api.py:146` | 30 min |
| 3 | 🔐 Seguridad | Salt aleatorio para PBKDF2 + migración de perfiles | `storage.py:40` | 2 hrs |
| 4 | 🔐 Seguridad | Eliminar o limitar `DISABLE_API_AUTH` | `api.py:73-74` | 15 min |
| 5 | 🏗️ Arquitectura | Refactorizar `launch_browser()` — tipo único `BrowserResources` | `base.py:77-160` | 4 hrs |
| 6 | 🏗️ Arquitectura | Singleton de captcha solver en API (lazy-init al startup) | `api.py:176-188` | 1 hr |
| 7 | 🚀 DevOps | ENTRYPOINT del Dockerfile → `tramites` | `Dockerfile` | 15 min |
| 8 | 🚀 DevOps | Secrets CI → GitHub Secrets | `.github/workflows/ci.yml` | 30 min |
| 9 | 🚀 DevOps | Push Docker image a GHCR | `.github/workflows/ci.yml` | 1 hr |

### 🟡 Semana 2: Deuda Técnica Alta

| # | Área | Acción | Esfuerzo |
|---|------|--------|----------|
| 10 | 🏗️ Arq | Cache LRU de resultados (compartir entre módulos) | 1 día |
| 11 | 🏗️ Arq | Rate limiting por portal (no global) | 0.5 día |
| 12 | 🏗️ Arq | Agregar 12 endpoints faltantes a API REST | 2 días |
| 13 | ⚡ Perf | Browser pool: health check + max_uses | 2 días |
| 14 | ⚡ Perf | requests.Session para HTTP pooling | 0.5 día |
| 15 | ⚡ Perf | Log rotation (RotatingFileHandler) | 0.5 día |
| 16 | 🚀 DevOps | Mover 13 .md de raíz a docs/ | 1 hr |
| 17 | 🚀 DevOps | Release workflow con etiquetas + GHCR | 1 día |
| 18 | 🧪 Testing | Ejecutar coverage + fail_under=60 | 1 hr |
| 19 | 🧪 Testing | Testear free_captcha.py y browser_pool.py | 1 día |

### 🟢 Semana 3: Mejoras y Pulido

| # | Área | Acción | Esfuerzo |
|---|------|--------|----------|
| 20 | 🎨 UI/UX | Refactorizar routing con session_state | 0.5 día |
| 21 | 🎨 UI/UX | Manejo de errores específicos con sugerencias | 1 día |
| 22 | 🎨 UI/UX | Agregar @st.cache_data para datos estáticos | 0.5 día |
| 23 | 🎨 UI/UX | Sistema de progreso para operaciones largas | 1 día |
| 24 | 🏗️ Arq | Extraer servicios de BaseModule (Browser, Captcha, PDF) | 2-3 días |
| 25 | ⚡ Perf | Logger async con aiofiles | 1 día |
| 26 | ⚡ Perf | Parallelizar tramite_ambos con asyncio.gather | 1 día |
| 27 | 🔐 Seguridad | TLS verification en IMAP | 0.5 día |
| 28 | 🧪 Testing | Agregar ruff rules (B, SIM, ARG, RUF) | 0.5 día |
| 29 | 🧪 Testing | Configurar mypy strict | 0.5 día |

### 🔵 Semana 4+: Refactorización Mayor

| # | Área | Acción | Esfuerzo |
|---|------|--------|----------|
| 30 | 🏗️ Arq | Unificar dispatch: eliminar modo_directo | 1 día |
| 31 | 🏗️ Arq | Pool de contexts (no solo browsers) | 2 días |
| 32 | 🧪 Testing | Tests de integración con Playwright real | 2 días |
| 33 | 🧪 Testing | Smoke test + snapshot testing | 1 día |
| 34 | 🚀 DevOps | Reducir imagen Docker 2-3GB → <1GB | 2 días |
| 35 | 🚀 DevOps | Devcontainer | 1 día |
| 36 | 🎨 UI/UX | .streamlit/config.toml + tema personalizado | 0.5 día |
| 37 | 🚀 DevOps | Seguridad: pip-audit en CI | 0.5 día |

---

## Tabla de Prioridades Completa

| Prio | Área | ID | Descripción | Esfuerzo | Impacto |
|------|------|----|-------------|----------|---------|
| 🔴 | Seg | C1 | Eliminar --no-sandbox | 15min | Crítico |
| 🔴 | Seg | C2 | CORS restrictivo en prod | 30min | Crítico |
| 🔴 | Seg | C3 | Salt aleatorio PBKDF2 | 2h | Crítico |
| 🔴 | Seg | C4 | Eliminar DISABLE_API_AUTH | 15min | Crítico |
| 🔴 | Arq | H1 | Refactor launch_browser() tipo único | 4h | Crítico |
| 🔴 | Arq | H6 | Singleton captcha solver | 1h | Alto |
| 🔴 | Arq | H3 | Agregar endpoints API faltantes | 2d | Alto |
| 🔴 | Perf | P1 | Browser pool health check + max_uses | 2d | Alto |
| 🔴 | Perf | P3 | Cache LRU de resultados | 1d | Alto |
| 🔴 | DevOps | D1 | ENTRYPOINT Dockerfile | 15min | Crítico |
| 🔴 | DevOps | D2 | Secrets CI → GitHub Secrets | 30min | Crítico |
| 🔴 | DevOps | D3 | Push Docker image a GHCR | 1h | Alto |
| 🟡 | Arq | H4 | Rate limiting por portal | 4h | Alto |
| 🟡 | Arq | T2 | Unificar dispatch tramites | 1d | Medio |
| 🟡 | Perf | P2 | Logger async con aiofiles | 1d | Alto |
| 🟡 | Perf | P4 | requests.Session HTTP pooling | 4h | Alto |
| 🟡 | Perf | P5 | Whisper warmup | 2h | Alto |
| 🟡 | Testing | R1 | Coverage report + fail_under | 1h | Alto |
| 🟡 | Testing | R2 | Testear free_captcha.py | 1d | Alto |
| 🟡 | Testing | R3 | Testear browser_pool.py | 1d | Alto |
| 🟡 | DevOps | D4 | Release workflow + GHCR push | 1d | Alto |
| 🟡 | DevOps | D5 | Mover 13 .md a docs/ | 1h | Medio |
| 🟡 | UI/UX | UX1 | Routing con session_state | 4h | Alto |
| 🟡 | UI/UX | UX3 | Progress bars + cancelación | 1d | Alto |
| 🟡 | UI/UX | UX4 | Errores específicos | 1d | Alto |
| 🟢 | Arq | T1 | Extraer servicios de BaseModule | 3d | Medio |
| 🟢 | Arq | T3 | Ampliar PII sanitization | 1d | Medio |
| 🟢 | Perf | P6 | Log rotation | 2h | Medio |
| 🟢 | Testing | R4 | Configurar mypy strict | 2h | Medio |
| 🟢 | Testing | R5 | Agregar ruff rules | 1h | Bajo |
| 🟢 | Seg | M1 | TLS verification IMAP | 2h | Medio |
| 🟢 | DevOps | D6 | Devcontainer | 1d | Bajo |
| 🟢 | DevOps | D7 | Reducir imagen Docker | 2d | Medio |

---

## Scoreboard Proyectado

| Dimensión | Actual | Post-Semana 1 | Post-Semana 2 | Post-Semana 4 |
|-----------|--------|---------------|---------------|---------------|
| code_quality | 7.5 | 7.5 | 8.0 | 8.5 |
| test_coverage | 7.5 | 7.5 | 8.0 | 8.5 |
| security | 8.5 | 9.5 | 9.5 | 9.5 |
| architecture | 8.0 | 8.5 | 9.0 | 9.0 |
| error_handling | 7.5 | 8.0 | 8.0 | 8.5 |
| performance | 7.5 | 7.5 | 8.5 | 9.0 |
| documentation | 6.0 | 6.0 | 7.0 | 8.0 |
| maintainability | 7.5 | 7.5 | 8.0 | 8.5 |
| observability | 7.5 | 7.5 | 8.0 | 8.5 |
| config_mgmt | 8.0 | 8.5 | 9.0 | 9.0 |
| devops | 8.0 | 8.5 | 9.0 | 9.5 |
| **TOTAL** | **8.0** | **8.3** | **8.7** | **9.0** |

---

## Filosofía del Plan

1. **Seguridad primero** — Semana 1 es 90% seguridad. Los 4 hallazgos críticos (--no-sandbox, CORS, salt, DISABLE_AUTH) son inmediatos.
2. **Estabilidad después** — Browser pool y API coverage evitan crashes silenciosos.
3. **UX al final** — La UI es funcional. Duele pero no es priority 1 cuando hay agujeros de seguridad.
4. **Testing como habilitador** — Coverage + CI + mypy habilitan refactorings seguros.

---

## Archivos de Referencia

| Archivo | Contenido |
|---------|-----------|
| `docs/mejoras/ANALISIS-ARQUITECTURA-BACKEND.md` | Arquitectura, deuda técnica, 6 hallazgos críticos |
| `docs/mejoras/ANALISIS-SEGURIDAD.md` | 4 vulnerabilidades críticas, 7 medias |
| `docs/mejoras/ANALISIS-UI-UX.md` | 6 problemas críticos UX, puntaje 2.3/5 |
| `docs/mejoras/ANALISIS-TESTING-CALIDAD.md` | Gaps de cobertura, infraestructura, prioridades |
| `docs/mejoras/ANALISIS-PERFORMANCE.md` | 5 cuellos de botella, mapa térmico, métricas |
| `docs/mejoras/ANALISIS-INFRA-DEVOPS.md` | Docker, CI/CD, git hooks, documentación |
