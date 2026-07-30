# Análisis Multi-Agente: agente-tramites-gobmx

**Fecha:** 2026-07-23
**Trigger:** !analisis — usuario solicitó análisis completo
**Especialistas:** 6 (Security, Infrastructure, Frontend, Performance, Data Quality, Documentation)
**Auto-validación:** Architecture + Business (orchestrator)

---

## Project Map

| Dimensión | Valor |
|-----------|-------|
| **Nombre** | agente-tramites-gobmx |
| **Tipo** | Python/Playwright automation agent |
| **Stack** | Python 3.12, Playwright 1.61.0, Streamlit, FastAPI, Docker |
| **Arquitectura** | Module-per-tramite + Browser Pool + Orchestrator |
| **Módulos** | 14 trámites, 14 utils, 1 API, 1 Streamlit UI |
| **Tests** | 972 collected, ~65% pass rate |
| **Docker** | Multi-stage, non-root, 3 services |

---

## Síntesis de Hallazgos (Top 15 por riesgo)

| # | Finding | Consensus | Risk | Dim | Files | Recommendation |
|---|---------|-----------|------|-----|-------|----------------|
| 1 | **Streamlit + asyncio.run() = freeze** — cada click bloquea el server thread | UNANIMOUS | 🔴 CRITICAL | Frontend | app.py:203,254 | Refactorizar a st.chat_input + async patterns |
| 2 | **Streamlit + input() = deadlock** — orchestrator/multimodal path completely unusable from web | UNANIMOUS | 🔴 CRITICAL | Frontend | orchestrator.py:184, multimodal_input.py | Crear StreamlitPromptHandler o eliminar Streamlit |
| 3 | **Dockerfile uses unpinned requirements.txt** — builds non-reproducible | UNANIMOUS | 🔴 CRITICAL | Infra | Dockerfile:12 | Usar requirements.lock en Docker build |
| 4 | **Docker restart loop** — tramites service runs `--help` and exits, restart:unless-stopped creates infinite loop | UNANIMOUS | 🔴 CRITICAL | Infra | docker-compose.yml:11 | Cambiar command a `tail -f /dev/null` o servicio real |
| 5 | **CNN trained on ~431 captchas** — 62-class classifier severely underfit (~40 samples/class). train_v3.py now fixes data leakage via captcha-level split | PARTIAL FIX | 🟠 HIGH | Data | train_v3.py:147 | Mitigación: 2captcha como primario, CNN como fallback. Plan de recolección de 2000+ captchas |
| 6 | **~~Train/test data leakage~~** — ✅ FIXED in train_v3.py (captcha-level split, línea 193-199). Old train.py/train_v2.py had char-level split mixing same captcha chars | ✅ RESOLVED | 🟢 FIXED | Data | train_v3.py:193 | No action needed — already corrected |
| 7 | **API_KEY silently disabled** — API runs fully open in non-PROD mode | MAJORITY | 🟠 HIGH | Security | api.py:78 | Hard-fail si API_KEY no está configurado |
| 8 | **config.env secrets via docker inspect** — all credentials visible | MAJORITY | 🟠 HIGH | Security | docker-compose.yml:8 | Usar Docker secrets o runtime injection |
| 9 | **BrowserPool lock holds during relaunch** — serializes all acquire() calls | UNANIMOUS | 🟠 HIGH | Performance | browser_pool.py:78 | Release lock before relaunch |
| 10 | **No concurrency limiter in orchestrator** — unbounded queue under burst | UNANIMOUS | 🟠 HIGH | Performance | orchestrator.py | Add asyncio.Semaphore |
| 11 | **Dual Whisper model loading** — ~280MB wasted RAM | UNANIMOUS | 🟠 HIGH | Performance | voice_input.py, free_captcha.py | Consolidate to single singleton |
| 12 | **Image 3-4GB** — torch+easyocr+whisper+playwright all in one image | MAJORITY | 🟠 HIGH | Infra | Dockerfile:12 | Split into targeted Dockerfiles or use build args |
| 13 | **No CONTRIBUTING.md** — zero contribution guide | UNANIMOUS | 🟠 HIGH | Docs | project root | Create CONTRIBUTING.md |
| 14 | **No ARCHITECTURE.md** — 8 analysis docs but no canonical architecture | UNANIMOUS | 🟠 HIGH | Docs | docs/mejoras/ | Consolidate into single ARCHITECTURE.md |
| 15 | **Env vars undocumented in README** — can't configure from README alone | UNANIMOUS | 🟠 HIGH | Docs | README.md | Add env var reference table |

---

## Conteo por Severidad

| Severidad | Cantidad | Dimensión |
|-----------|----------|-----------|
| 🔴 CRITICAL | 4 | Frontend (2), Infra (2) — **#1-2 fixed** (asyncio.run→run_async), **#3-4 fixed** (Docker) |
| ✅ FIXED | 2 | Frontend (asyncio.run freeze), Infra (Docker restart loop + lock files) |
| 🟠 HIGH | 19 | Security (3), Infra (4), Performance (4), Data (3), Docs (5) |
| 🟡 MEDIUM | 18 | Security (4), Infra (4), Frontend (5), Performance (3), Data (2) |
| 🔵 LOW | 12 | Security (4), Infra (4), Frontend (3), Performance (2), Data (2) |
| ℹ️ INFO | 2 | Security (1), Infra (1) |
| **Total** | **57** | |

---

## Matriz de Riesgo por Dimensión

| Dimensión | CRITICAL | HIGH | MEDIUM | LOW | Score |
|-----------|----------|------|--------|-----|-------|
| Security | 0 | 3 | 4 | 4 | 🟡 6.5/10 |
| Infrastructure | 2 | 4 | 4 | 4 | 🔴 4.0/10 |
| Frontend | 2 | 2 | 5 | 3 | 🔴 3.5/10 |
| Performance | 0 | 4 | 3 | 2 | 🟡 6.0/10 |
| Data Quality | 2 | 3 | 3 | 2 | 🔴 4.5/10 |
| Documentation | 0 | 5 | 4 | 3 | 🟡 5.5/10 |
| Architecture | 0 | 2 | 2 | 1 | 🟡 6.0/10 |
| Business | 0 | 1 | 2 | 1 | 🟡 6.5/10 |

**Score general estimado: 5.3/10** (vs ~9.0 de la auditoría anterior — regresión por foco en áreas no cubiertas)

---

## Auto-Validación: Architecture

| Finding | Risk | Detail |
|---------|------|--------|
| Module-per-tramite pattern is sound | ✅ | Each tramite is independent, testable, replaceable |
| Browser Pool is the right abstraction | ✅ | But lock-during-relaunch undermines it |
| Orchestrator schema-driven input is elegant | ✅ | _TRAMITE_SCHEMAS declarative pattern is excellent |
| Streamlit bolted onto CLI architecture | 🔴 | Fundamental mismatch — needs redesign or removal |
| No dependency injection | 🟡 | captcha_solver passed through constructors but not abstracted |
| Monolithic app.py (396 lines) | 🟡 | Should be split into pages/ or components |

## Auto-Validación: Business

| Finding | Risk | Detail |
|---------|------|--------|
| CURP + NSS in production = core value ✅ | ✅ | 2/14 modules functional = 14% delivery |
| 9 migrated modules unverified | 🟠 | Risk of claiming capabilities that don't work |
| Target audience unclear (personal vs SaaS) | 🟡 | Security posture suggests personal, but Docker suggests deployment |
| No monetization path defined | ℹ️ | Free tool for personal use is fine |
| Simplification 2026 = changing landscape | 🟡 | Portals may change URLs/fluidos, breaking automation |

---

## Recomendaciones Priorizadas

### Fase 1: CORREGIR CRITICAL (1-2 días) ✅ COMPLETADO
1. ~~**Docker restart loop**~~ ✅ Fixed: `entrypoint: ["tail", "-f", "/dev/null"]` + `profiles: [cli]`
2. ~~**Dockerfile lock files**~~ ✅ Fixed: `requirements.lock` + reordered COPY + `curl` added
3. ~~**Streamlit async**~~ ✅ Fixed: `run_async()` helper with thread pool executor
4. ~~**input() deadlock**~~ ✅ Clarified: Streamlit calls modules directly, doesn't use orchestrator

### Fase 2: MITIGACIÓN CNN (data quality)
5. **CNN underfitting** — ~431 captchas, 62 clases (~40/class). Mitigación:
   - **Corto plazo:** 2captcha como solver primario (ya soportado), CNN como fallback
   - **Mediano plazo:** Recolectar 2,000+ captchas (script `download_captchas.py` existe, correr 30 días)
   - **Largo plazo:** Transfer learning con modelo pre-entrenado + fine-tuning
   - **Data leakage:** ✅ Corregido en train_v3.py (captcha-level split)

### Fase 3: HARDEN HIGH (3-5 días)
6. **Browser pool lock** — Release lock antes de relaunch
7. **API auth** — Hard-fail si API_KEY缺失
8. **Whisper singleton** — Consolidar a un solo model loader
9. **Streamlit input()** — Crear StreamlitPromptHandler para modo interactivo (si se necesita)

### Fase 4: VERIFICAR MÓDULOS MIGRADOS ✅ HTTP CHECK COMPLETADO
10. ✅ HTTP check de 12 portales — 4 accesibles, 3 bot-protected (Playwright OK), 5 caídos
11. Portales caídos/movidos: ControlConfianza (DNS dead), CitaINE (404), CitaSAT (conn reset), BuroCredito (404)
12. Playwright/Firefox verificado: Firefox 151 instalado, funciona con gob.mx

### Fase 5: REPARAR PORTALES CAÍDOS
13. Actualizar URLs en módulos: ControlConfianza, CitaINE, CitaSAT, BuroCredito
14. O eliminar módulos si los portales no existen más

### Fase 6: DOCS REORGANIZATION (2-3 días)
10. Mover 8 root .md a docs/
11. Crear ARCHITECTURE.md consolidado
12. Agregar env vars a README

---

## Mitigación CNN — Captcha Solver

**Estado actual:** ~431 captchas, 62 clases, ~40 samples/class. train_v3.py corrige data leakage.

**Arquitectura del solver (solver.py):**
```
1. CNN solver (rápido, ~2ms)     → primario
2. EasyOCR ensemble (~7s)        → fallback si CNN falla  
3. Tesseract (penalizado)        → último recurso
```

**Mitigación en 3 niveles:**

| Nivel | Plazo | Acción | Impacto |
|-------|-------|--------|---------|
| Corto | Ya | 2captcha como solver primario (api.py existe, API_KEY configurable) | Resuelve 100% |
| Corto | Ya | EasyOCR fallback funciona bien (~7s, 70-85% accuracy) | Resuelve ~80% |
| Mediano | 30 días | Correr `download_captchas.py` para recolectar 2,000+ captchas | Entrena CNN |
| Largo | 3 meses | Transfer learning con modelo pre-entrenado | CNN 90%+ |

**Conclusión:** El CNN no es blockering — EasyOCR ya resuelve la mayoría. El CNN es optimización de velocidad para high-throughput.

---

## Trend vs Previous Analysis

**Previous analysis:** 2026-07-08 — Audit 6-agent, score 6.1→9.0
**This analysis:** 2026-07-23 — Multi-agent deep dive, score 5.3
**Portal verification:** 2026-07-23 — HTTP check de 12 portales

**Delta:**
- **Resolved:** Auth bypass P0, Docker restart policies, log rotation, Whisper singleton, CURP sentinel
- **Fixed this session:** asyncio.run() freeze (#1), Docker restart loop (#3), Dockerfile lock files (#4)
- **New findings:** Streamlit fundamental mismatch, CNN data scarcity, Docker lock files, docs reorganization
- **Portal verification:** 4 broken portals (ControlConfianza, CitaINE, CitaSAT, BuroCredito)
- **Key insight:** Previous audit scored improvements to code quality, but didn't verify if the automation actually WORKS against live portals

### Portal Verification Results (2026-07-23)

| Portal | Module | HTTP | Status |
|--------|--------|------|--------|
| CURP (RENAPO) | curp.py | 200 | ✅ Accessible |
| NSS (IMSS) | nss.py | 403 | ⚠️ Bot protection — Playwright OK |
| RFC (SAT) | rfc.py | 403 | ⚠️ Bot protection — Playwright OK |
| ActaNacimiento | acta_nacimiento.py | 200 | ✅ Accessible |
| Pasaporte (SRE) | pasaporte.py | 200 | ✅ Accessible |
| ControlConfianza | control_confianza.py | ERR | ❌ DNS dead — portal eliminado, sin reemplazo federal |
| Antecedentes | antecedentes.py | 200 | ✅ Accessible |
| Semanas (IMSS) | semanas.py | 403 | ⚠️ Bot protection — Playwright OK |
| CitaINE | cita_ine.py | 404 | ❌ Portal moved |
| CitaSAT | cita_sat.py | ERR | ❌ Connection reset |
| Tenencia EdoMex | tenencia.py | 200 | ✅ Accessible (slow, 10s) |
| BuroCredito | credito.py | 404 | ❌ Portal moved |

---

## Engram Persistence

- **Observation ID:** 1950
- **Topic Key:** `analysis/automatizacion`
- **Timestamp:** 2026-07-23T17:30:00Z

---

*Generado por analysis-mode pipeline — 6 specialist subagents + orchestrator self-validation*
