# ROADMAP COMPLETO — Agente de Trámites GOB.MX

## 📋 ¿De qué va este proyecto?

**Agente automatizador de trámites gubernamentales mexicanos** vía web scraping con Playwright. Reduce trámites de 10-25 min manuales a **<2 min automatizados**.

### Stack actual

| Componente | Tecnología |
|---|---|
| Core | Python 3.10+ ~3.14 |
| Scraping | Playwright (Firefox + Chrome) |
| Captcha pago | 2captcha.com API |
| Captcha gratis | Tesseract OCR + Whisper (audio reCAPTCHA) |
| Captcha IMSS (propio) | **CNN PyTorch + ONNX** — 11 modelos, ~85% char acc |
| OCR general | pytesseract + EasyOCR + OpenCV |
| Voz | Whisper + sounddevice |
| Email | IMAPClient |
| Perfiles | cryptography.fernet (encriptado local) |
| Tests | pytest + pytest-asyncio (24 tests, 3 suites) |
| **Base code** | **70 .py files, 13,536 líneas, 109.6 MB modelos** |

### Trámites soportados

| Trámite | Portal | Estado | Tiempo |
|---|---|---|---|
| **CURP** (consulta + PDF) | RENAPO | ✅ **PRODUCCIÓN** | ~16s |
| **NSS IMSS** | Portal IMSS | ✅ **PRODUCCIÓN** | ~30-60s |
| Antecedentes No Penales | — | 🔶 Escrito, sin testear | ~45-90s |
| Tenencia Vehicular | — | 🔶 Escrito, sin testear | ~20-40s |

**8 trámites más identificados como factibles** en `ANALISIS_TRAMITES_GOB_MX.md` pero **NO implementados**.

---

## 🗺️ ROADMAP POR FASES

### FASE 0: CONSOLIDACIÓN ESTRUCTURAL (Alta prioridad — base quebrada)
*Duración estimada: 1-2 sprints*

| # | Tarea | Impacto | Riesgo |
|---|---|---|---|
| 0.1 | 🎯 **Eliminar duplicación src/ vs raíz** — unificar a UN solo entry point, un solo `modules/`, un solo `utils/` | 🔴 CRÍTICO | Rotura temporal de imports |
| 0.2 | 🎯 **Refactorizar NSSModule** para heredar de BaseModule (hoy tiene su propio browser lifecycle duplicado) | 🔴 CRÍTICO | Puede romper NSS |
| 0.3 | **Estandarizar error handling**: eliminar `except Exception` genéricos, crear tes jerarquía de excepciones propia | 🟡 ALTO | Bajo |
| 0.4 | **Unificar logging**: reemplazar `print()` por logging estructurado en TODOS los módulos | 🟡 ALTO | Bajo |
| 0.5 | **Crear pyproject.toml / setup.py** — que sea instalable como paquete | 🟢 MEDIO | Bajo |

**Verificación**: `pytest tests/`, `python -c "from modules import *"`, ejecutar CURP+NSS end-to-end.

---

### FASE 1: SEGURIDAD Y SECRETOS (Alta prioridad — hoy hay riesgos)
*Duración: 1 sprint*

| # | Tarea | Impacto | Riesgo |
|---|---|---|---|
| 1.1 | 🎯 **Reemplazar config.env plano por secrets manager** (Windows Credential Manager o vault local encriptado) | 🔴 CRÍTICO | Medio |
| 1.2 | 🎯 **Verificar que config.env NO esté trackeado en git** — `git rm --cached` si es necesario | 🔴 CRÍTICO | Bajo |
| 1.3 | **Implementar hashing de contraseñas** en `save_profile()` (hoy guarda texto plano) | 🟡 ALTO | Bajo |
| 1.4 | **Sanitizar captcha solver**: validar input de imágenes contra injection | 🟢 MEDIO | Bajo |
| 1.5 | **Rate limiting + User-Agent rotation** para evitar bloqueo por scraping | 🟡 ALTO | Bajo |

**Verificación**: `git ls-files config.env` → vacío, inspección visual de profiles.json, prueba de scraping 3x seguidas.

---

### FASE 2: RENDIMIENTO Y OPTIMIZACIÓN
*Duración: 1-2 sprints*

| # | Tarea | Impacto | Riesgo |
|---|---|---|---|
| 2.1 | 🎯 **Browser pool + reutilización**: hoy cada trámite abre/cierra Firefox (~3-5s overhead). Pool persistente | 🟡 ALTO | Medio |
| 2.2 | **Reducir tiempos de captcha**: EasyOCR fallback tarda ~7s. Mejorar CNN o cachear resoluciones | 🟡 ALTO | Medio |
| 2.3 | **Optimizar carga de modelos CNN**: hoy carga 11 checkpoints en disco (~110 MB). Cargar solo el mejor vía ONNX | 🟢 MEDIO | Bajo |
| 2.4 | **Compresión de perfiles**: profiles.json en texto plano, podría ser SQLite embebido | 🟢 MEDIO | Medio |
| 2.5 | **Caché de selectores CSS** que persista entre sesiones (evitar re-descubrir) | 🟢 MEDIO | Bajo |

**Verificación**: Benchmark con `_benchmark.py` o script ad-hoc midiendo tiempos por trámite antes/después.

---

### FASE 3: TESTS DE INTEGRACIÓN Y ROBUSTEZ
*Duración: 1-2 sprints*

| # | Tarea | Impacto | Riesgo |
|---|---|---|---|
| 3.1 | 🎯 **Tests de integración contra portales reales** (RENAPO, IMSS) usando fixtures de captcha real | 🔴 CRÍTICO | Medio |
| 3.2 | **Sistema de health checks diarios**: script que verifique que los selectores CSS sigan funcionando | 🟡 ALTO | Bajo |
| 3.3 | **Snapshot testing**: capturar HTML de portales y comparar ante cambios | 🟡 ALTO | Medio |
| 3.4 | **Aumentar dataset CNN a >2000 captchas** etiquetados para mejorar accuracy (>95%) | 🟡 ALTO | Medio |
| 3.5 | **Implementar reintentos automáticos** con backoff ante fallos de red/portal | 🟢 MEDIO | Bajo |

**Verificación**: `pytest tests/ --integration`, ejecutar health-check, validar accuracy CNN.

---

### FASE 4: NUEVOS TRÁMITES (Alto valor de negocio)
*Duración: 2-3 sprints*

Priorizados por factibilidad + valor:

| # | Trámite | Valor estimado | Dificultad |
|---|---|---|---|
| 4.1 | **RFC / Constancia Fiscal SAT** | $$$ (demanda masiva) | Alta (reCAPTCHA v2) |
| 4.2 | **Semanas cotizadas IMSS** | $$ | Media |
| 4.3 | **Cita Pasaporte** | $$ | Media |
| 4.4 | **Cita INE** | $ | Alta (compleja) |
| 4.5 | **Pago de Tenencia** (hoy solo consulta) | $$ | Media |
| 4.6 | **Cita Licencia** | $ | Media |
| 4.7 | **Cita RFC SAT** | $$ | Alta |

**Verificación**: Cada trámite con su propio test de integración + benchmark de tiempo.

---

### FASE 5: INFRAESTRUCTURA Y DEVOPS
*Duración: 1-2 sprints*

| # | Tarea | Impacto | Riesgo |
|---|---|---|---|
| 5.1 | **Dockerizar la aplicación** para entornos reproducibles | 🟡 ALTO | Medio |
| 5.2 | **CI/CD pipeline** (GitHub Actions) con lint + test + benchmark | 🟡 ALTO | Bajo |
| 5.3 | **Sentry o error tracking** para monitoreo en producción | 🟢 MEDIO | Bajo |
| 5.4 | **API REST** para exponer trámites como servicio | 🟢 MEDIO | Alto |
| 5.5 | **Web UI mínima** (Streamlit o FastAPI + Jinja) para uso no-CLI | 🟢 MEDIO | Alto |

**Verificación**: `docker build . && docker run`, GitHub Actions pasando todos los tests.

---

### FASE 6: CAPTCHA CNN — LLEVAR A 99%
*Duración: 2 sprints (puede correr en paralelo con F4/F5)*

| # | Tarea | Impacto | Riesgo |
|---|---|---|---|
| 6.1 | **Generar dataset sintético** con augmentations (rotación, ruido, distorsión) | 🟡 ALTO | Bajo |
| 6.2 | **Implementar curriculum learning**: entrenar progresivamente con datos más duros | 🟡 ALTO | Medio |
| 6.3 | **Probar arquitecturas modernas** (CRNN+CTC, ViT tiny) contra OriginalCNN | 🟢 MEDIO | Medio |
| 6.4 | **Auto-labeling**: usar ensemble de modelos existentes para etiquetar nuevos captchas | 🟡 ALTO | Medio |
| 6.5 | **Deploy como microservicio** (FastAPI + ONNX Runtime) para baja latencia | 🟢 MEDIO | Medio |

**Verificación**: Accuracy en test set >95% chars, >90% captchas completos.

---

## ✅ GAP ANALYSIS #1 — RENDIMIENTO Y OPTIMIZACIÓN

### Estado actual
| Métrica | Valor | Target | Gap |
|---|---|---|---|
| CURP tiempo | ~16s | <10s | ⚠️ 60% overhead |
| NSS tiempo | ~30-60s | <20s | ⚠️ 50-200%+ overhead |
| Captcha CNN inferencia | ~2-8ms | <5ms | ✅ OK |
| EasyOCR fallback | ~7s | <1s | 🔴 **700% gap** |
| Browser startup | ~3-5s (cada vez) | <500ms (pool) | 🔴 **600-1000% gap** |
| Modelos CNN en disco | 109.6 MB | <20 MB (ONNX solo) | 🔴 **548% gap** |
| Import startup | ~2-3s (Whisper!) | <500ms | ⚠️ 400-600% gap |

### Causas raíz

1. **No hay browser pooling** → cada trámite abre Firefox desde cero (3-5s perdidos)
2. **Whisper se importa siempre** aunque no se use voz → import de ~2-3s (lazy import needed)
3. **EasyOCR fallback es lentísimo** → 7s por captcha; ocurre cuando CNN da baja confianza
4. **Modelos CNN se cargan todos** → 109.6 MB de checkpoints en disco contra ~20 MB del ONNX
5. **OCR ensemble en captcha** ejecuta 5 variantes de preprocessing + 2 OCR engines → overshoot para lo que necesita

### Recomendaciones inmediatas

- **Lazy imports**: mover `import whisper` y `import easyocr` a funciones, no al tope del módulo
- **Browser pool**: implementar `PlaywrightPool` con max 2 browsers persistentes
- **ONNX-only mode**: cargar solo modelo ONNX (~10 MB, ~2ms inf) en vez de todos los .pt
- **Cache de resoluciones captcha**: TTL corto (~60s) para mismo captcha repetido
- **Perfiles a SQLite**: reducir I/O de JSON plano a queries indexadas

---

## ✅ GAP ANALYSIS #2 — SEGURIDAD Y USO DE RECURSOS

### Vector de ataque / Riesgo

| Riesgo | Severidad | Estado actual | Remedio |
|---|---|---|---|
| **Credenciales en .env plano** | 🔴 **CRÍTICO** | API keys + IMAP pass + STORAGE_KEY en texto plano en config.env | Windows Credential Manager o vault encriptado |
| **config.env trackeado en git** | 🔴 **CRÍTICO** | `config.env` está en `.gitignore` pero requiere verificación | `git ls-files config.env` para confirmar |
| **Contraseñas sin hash en profiles** | 🟡 ALTO | `profiles.json` guarda passwords en texto plano (Fernet encrypt, pero la key está en config.env) | Hashing con bcrypt + clave de cifrado separada |
| **Errores genéricos silenciosos** | 🟡 ALTO | `except Exception: pass` en múltiples lugares | Sistema de excepciones propio + alertas |
| **Inyección vía captcha solver** | 🟢 MEDIO | CNN recibe imágenes, pero EasyOCR/Tesseract podrían procesar texto malicioso | Validar input antes de pasar a OCR |
| **Datos sensibles en logs** | 🟢 MEDIO | No hay sanitización de CURP/passwords en logs | Filtro de datos personales en logger |
| **Playwright sin aislamiento** | 🟢 MEDIO | El browser corre en el mismo proceso que las credenciales | Sandboxing del browser |

### Uso de recursos

| Recurso | Uso actual | Problema | Optimización |
|---|---|---|---|
| **Disco** | 109.6 MB modelos + logs + outputs | Modelos duplicados (.pt + .onnx) | Mantener solo ONNX (~20 MB) |
| **RAM** | ~300-500 MB por trámite (browser + pytorch) | Browser abierto todo el ciclo | Pool con max 2 browsers |
| **GPU** | No usa | PyTorch cargado en RAM aunque CNN sea CPU | `torch.device("cpu")` explícito |
| **Red** | ~5-15 requests por trámite | Sin rate limiting | Throttle + User-Agent rotation |
| **CPU** | ~30-50% durante OCR | EasyOCR + Whisper son CPU-bound | ONNX Runtime + threading |

### Recomendaciones inmediatas
1. 🔴 Mover secrets a Windows Credential Manager YA
2. 🔴 Verificar que `config.env` no esté en git history
3. 🟡 bcrypt en profiles.json
4. 🟡 Sanitizer de logs (CURP mascarado)
5. 🟢 ONNX-only → libera 90 MB de disco

---

## ✅ GAP ANALYSIS #3 — CARGA Y ESCALABILIDAD

### Escenarios de carga

| Escenario | Funciona hoy? | Problema |
|---|---|---|
| **1 usuario, 1 trámite** | ✅ Sí | Perfecto |
| **1 usuario, 5 trámites seguidos** | ⚠️ Lento | Browser se abre/cierra cada vez → 15-25s overhead acumulado |
| **5 usuarios simultáneos** | ❌ No | No hay concurrencia — todo es secuencial |
| **10+ trámites/día** | ⚠️ Posible | Sin rate limiting → IP bloqueada por scraping |
| **Escalar a 100 trámites/día** | ❌ No | Sin Docker, sin cola de workers, sin proxies |
| **API expuesta** | ❌ No | Solo CLI |

### Arquitectura actual vs. escalable

| Aspecto | Hoy | Necesario para escalar |
|---|---|---|
| **Concurrencia** | Asyncio pero secuencial | Pool de workers + cola de jobs |
| **Browser** | 1 por trámite, se cierra | Pool persistente + aislamiento |
| **Rate limiting** | ❌ No existe | Throttle + proxies rotativos |
| **Cache** | ❌ No existe | Redis o SQLite para captchas y perfiles |
| **Cola** | ❌ No existe | RabbitMQ / Redis Queue para jobs async |
| **Monitoreo** | ❌ No existe | Prometheus + Grafana o Sentry |
| **Despliegue** | Script local | Docker + CI/CD |

### Cuello de botella principal

**El scraping es secuencial y monolítico.** Cada trámite bloquea todo el proceso. Con 2 trámites simultáneos, el segundo espera al primero.

**Caso real**: si querés CURP + NSS + Antecedentes en simultáneo, hoy tenés que esperar ~1.5 min secuencial. Con workers paralelos sería ~30s.

### Recomendaciones para escalabilidad

1. **Worker pool**: 3-5 workers async con browser pool compartido
2. **Cola de jobs**: Redis Queue o simple asyncio.Queue para encolar trámites
3. **Proxies rotativos**: 5+ proxies residenciales para evitar rate limiting
4. **Cache de sesiones**: reutilizar cookies de portales entre requests
5. **API REST mínima**: FastAPI + job queue para exponer como servicio
6. **Docker + KISS deploy**: Docker compose con worker + redis + API

---

## 📊 MATRIZ DE PRIORIDAD FINAL

| Fase | Prioridad | Esfuerzo | Impacto | Depende de |
|---|---|---|---|---|
| **F0 — Consolidación** | 🥇 1 | 2 sprints | 🔴 Elimina deuda técnica crítica | — |
| **F1 — Seguridad** | 🥇 1 | 1 sprint | 🔴 Riesgo de exposición | F0 (estructura) |
| **F2 — Rendimiento** | 🥈 2 | 2 sprints | 🟡 40-60% mejora tiempos | F0 |
| **F3 — Tests integración** | 🥈 2 | 2 sprints | 🟡 Detección temprana de roturas | F0 |
| **F4 — Nuevos trámites** | 🥉 3 | 3 sprints | 🟢 $ valor de negocio | F3 (para no romper) |
| **F5 — DevOps** | 🥉 3 | 2 sprints | 🟢 Despliegue reproducible | F0 |
| **F6 — Captcha 99%** | 🥉 3 | 2 sprints | 🟢 Mejora NSS | Independiente |

---

## ⚡ ACCIONES INMEDIATAS (Esta sesión)

Si querés arrancar YA los gaps más críticos:

```
1. Verificar config.env en git → git ls-files config.env
2. Refactor NSSModule → BaseModule (elimina ~200 líneas duplicadas)
3. Lazy imports: whisper, easyocr, torch → solo cuando se usan
4. Mover secrets a environment variables + .env.example actualizado
5. Browser pool básico (reutilizar instancia de Firefox)
```

¿Arrancamos con alguno?
