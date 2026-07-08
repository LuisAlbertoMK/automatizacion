# Plan de Mejoras Consolidado — Agente Automatización GOB.MX

**Fecha:** 6 de julio, 2026  
**Score actual:** 7.0/10  
**Score objetivo:** 8.5-9.0/10  
**Análisis realizado por:** 3 agentes especializados + web research (Playwright 2026)

---

## 📊 Resumen Ejecutivo

El proyecto tiene una **base arquitectónica sólida** con BaseModule bien abstraída, jerarquía de excepciones limpia, y separación en capas correcta. Sin embargo, existen problemas críticos de higiene del repo, seguridad, rendimiento y testing que limitan el score a 7.0.

**Hallazgos principales:**
- ✅ 394 tests con pytest (no 24 como decía docs)
- 🔴 22 archivos .py duplicados en raíz + 33 sys.path.insert hacks
- 🔴 7 input() bloqueantes en módulos async (rompe API REST)
- 🔴 Credenciales en config.env plano sin encriptación en reposo
- 🟡 Sin browser pool (3-5s overhead por trámite)
- 🟡 Imports pesados no-lazy (torch, whisper, easyocr)
- 🟡 Sin tests de integración contra portales reales

---

## 🎯 Plan de Implementación por Fases

### FASE 1: HIGIENE DEL REPO (CRÍTICO — 1 semana)

#### 1.1 Consolidar estructura de archivos
**Impacto:** ALTO | **Esfuerzo:** 4-5h | **Riesgo:** MEDIO

**Problema:** 22 archivos .py en raíz que no pertenecen al paquete:
- 2 wrappers redundantes (main.py, main_multimodal.py)
- 7 tests sueltos (test_curp_*.py, test_nss.py, etc.)
- 5 scripts internos (_analyze_errors.py, _benchmark.py, etc.)
- 4 scripts de verificación legacy (verificar_sistema.py, etc.)
- 6 archivos debug (debug_*.py)

**Acciones:**
1. Mover scripts de debug/benchmark a `tools/`
2. Eliminar wrappers main.py raíz (usar `src/main.py` o entry point pyproject.toml)
3. Consolidar 7 tests legacy en `tests/` o eliminar si son obsoletos
4. Eliminar scripts de verificación legacy (health_check.py es el canonical)
5. Verificar que `config.env` NO esté trackeado en git

**Verificación:**
```bash
git ls-files config.env  # Debe estar vacío
ls *.py  # Solo app.py y main.py (si se usa)
pytest tests/ -v  # Todos los tests pasan
```

#### 1.2 Resolver empaquetado Python
**Impacto:** ALTO | **Esfuerzo:** 3-4h | **Riesgo:** MEDIO

**Problema:** 33 ocurrencias de `sys.path.insert(0, ...)` en 33 archivos. El proyecto no funciona como paquete instalable malgré tener pyproject.toml.

**Acciones:**
1. Ajustar `pyproject.toml` con `packages = [{include = "src"}]`
2. Agregar `captcha_solver_imss` como subpaquete
3. Ejecutar `pip install -e .` para instalar en modo editable
4. Eliminar los 33 `sys.path.insert` manualmente
5. Verificar que `from modules.curp import CURPModule` funcione sin hacks

**Verificación:**
```bash
pip install -e .
python -c "from src.modules.curp import CURPModule; print('OK')"
grep -r "sys.path.insert" src/ tests/  # Debe estar vacío
```

#### 1.3 Corregir encoding roto
**Impacto:** BAJO | **Esfuerzo:** 30min | **Riesgo:** BAJO

**Problema:** Caracteres rotos en `utils/captcha.py`, `utils/ocr.py` y posiblemente otros (UTF-8 guardado como Latin-1).

**Acciones:**
1. Re-guardar archivos afectados como UTF-8 sin BOM
2. Verificar ~20 archivos con strings acentuados
3. Agregar `.editorconfig` con `charset = utf-8`

**Verificación:**
```bash
file src/utils/captcha.py  # Debe decir "UTF-8"
cat src/utils/captcha.py | grep -i "vía"  # Legible
```

---

### FASE 2: SEGURIDAD CRÍTICA (1 semana)

#### 2.1 Migrar secrets a Windows Credential Manager
**Impacto:** CRÍTICO | **Esfuerzo:** 2 días | **Riesgo:** MEDIO

**Problema:** Credenciales en config.env plano. Aunque .gitignore excluye config.env, cualquier backup o acceso físico expone las credenciales.

**Acciones:**
1. Ejecutar `store_all()` una vez para migrar secrets actuales
2. Verificar que todo funciona sin config.env
3. Eliminar fallback a `os.getenv()` en `secrets_manager.py` o agregar warning audible
4. Borrar config.env del disco

**Verificación:**
```bash
# Renombrar config.env temporalmente
mv config.env config.env.backup
python health_check.py  # Debe funcionar
# Si funciona, borrar backup
rm config.env.backup
```

#### 2.2 Salt único por instancia para STORAGE_KEY
**Impacto:** CRÍTICO | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** Salt hardcodeado `b"fernet-key-salt"` en storage.py:40. Dos usuarios con misma STORAGE_KEY generan misma clave Fernet.

**Acciones:**
1. Generar salt aleatorio de 16 bytes al crear STORAGE_KEY por primera vez
2. Guardar salt junto con perfiles (ej: `data/salt.bin`)
3. Usar ese salt para PBKDF2 en vez del literal hardcodeado

**Verificación:**
```python
# Crear perfil, verificar que salt se genera
python -c "from src.utils.storage import StorageManager; s = StorageManager(); s.save_profile('test', {'password': 'xxx'})"
ls data/salt.bin  # Debe existir
```

#### 2.3 Reemplazar PBKDF2 por bcrypt/argon2
**Impacto:** ALTO | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** PBKDF2-HMAC-SHA256 con 100K iteraciones es vulnerable a ataques GPU.

**Acciones:**
1. Agregar `bcrypt` o `argon2-cffi` a requirements.txt
2. Reemplazar `_hash_sensitive()` en storage.py con bcrypt (cost 12+) o argon2id
3. Migrar hashes existentes (re-hash en próximo login)

**Verificación:**
```python
# Verificar que passwords se hashean con bcrypt
python -c "from src.utils.storage import StorageManager; s = StorageManager(); s.save_profile('test', {'password': 'xxx'}); import json; print(json.load(open('data/profiles.enc')))"
```

#### 2.4 Eliminar except Exception: pass silenciosos
**Impacto:** ALTO | **Esfuerzo:** 3 días | **Riesgo:** BAJO

**Problema:** Más de 100 instancias de `except Exception` en todo el proyecto, muchas sin logging adecuado.

**Acciones:**
1. Reemplazar con `except Exception as e: logger.warning(f"...: {e}")`
2. Priorizar: secrets_manager.py, storage.py, base.py, logger.py
3. Agregar regla de linter para prohibir `except Exception: pass`

**Verificación:**
```bash
grep -r "except Exception:" src/ | wc -l  # Debe ser 0 o muy bajo
ruff check src/  # Sin warnings de bare except
```

#### 2.5 No mostrar API keys parciales en stdout/logs
**Impacto:** ALTO | **Esfuerzo:** 0.5 días | **Riesgo:** BAJO

**Problema:** auto_diagnostico.py:129 muestra primeros 8 caracteres de API key.

**Acciones:**
1. Reemplazar `api_key[:8]` por `"****"`
2. Mismo en app.py:232 y test_completo_curp.py:77
3. Agregar test que verifique que no se filtran secrets en logs

**Verificación:**
```bash
python auto_diagnostico.py | grep -i "api"  # No debe mostrar partial keys
```

#### 2.6 Agregar validación de inputs en todos los módulos
**Impacto:** ALTO | **Esfuerzo:** 2 días | **Riesgo:** BAJO

**Problema:** Solo src/main.py:445 y voice_input.py:322 validan formato CURP. Módulos reciben curp, correo, password sin validar.

**Acciones:**
1. Crear `utils/validators.py` con:
   - `validate_curp(curp: str) -> bool`
   - `validate_nss(nss: str) -> bool`
   - `validate_email(email: str) -> bool`
   - `validate_rfc(rfc: str) -> bool`
2. Llamar al inicio de cada `consultar()`
3. Sanitizar antes de pasar a `fill_field()`

**Verificación:**
```python
# Test de validación
python -c "from src.utils.validators import validate_curp; assert validate_curp('OOLL940914HMCRGS08'); assert not validate_curp('INVALID')"
```

---

### FASE 3: RENDIMIENTO (1-2 semanas)

#### 3.1 Implementar browser pool
**Impacto:** ALTO (3-5s mejora por trámite) | **Esfuerzo:** 3 días | **Riesgo:** MEDIO

**Problema:** Cada `consultar()` hace `launch_browser()` + `close_browser()`. Firefox tarda 2-4s en arrancar.

**Acciones:**
1. Crear `BrowserPool` con `asyncio.Queue`
2. Pre-lanzar 2-3 browsers al inicio
3. Cada módulo toma uno de la pool, lo usa, y lo devuelve
4. Agregar timeout de inactividad para cerrar browsers no usados

**Verificación:**
```python
# Benchmark antes/después
python _benchmark.py  # Comparar tiempos
```

#### 3.2 Lazy imports para torch, cv2, onnxruntime
**Impacto:** ALTO (10-15s mejora en startup) | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** `import torch` en tope de solver_v2.py tarda 5-10s.

**Acciones:**
1. Mover `import torch` dentro de `CNNSolverV2.__init__()`
2. Mismo para `cv2` en solver_v2.py:277
3. Usar módulo proxy si es necesario

**Verificación:**
```bash
# Medir tiempo de import
time python -c "from src.modules.nss import NSSModule"  # Debe ser <2s
```

#### 3.3 Reemplazar time.sleep() por await asyncio.sleep()
**Impacto:** MEDIO (1-5s mejora) | **Esfuerzo:** 0.5 días | **Riesgo:** BAJO

**Problema:** `time.sleep()` en captcha.py:288, mail_reader.py:62 bloquean event loop.

**Acciones:**
1. Reemplazar en captcha.py líneas 288, 303
2. Reemplazar en mail_reader.py línea 62
3. Reemplazar en voice_input.py línea 76

**Verificación:**
```bash
# Verificar que no hay time.sleep en código async
grep -n "time.sleep" src/utils/*.py  # Debe estar vacío o solo en código sync
```

#### 3.4 Caché de selectores CSS exitosos
**Impacto:** MEDIO (0.1-0.3s mejora por campo) | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** `fill_field()` itera por lista de selectores, haciendo `page.locator(sel).count()` por cada uno.

**Acciones:**
1. En BaseModule, agregar `self._selector_cache: dict[str, str] = {}`
2. Al encontrar selector exitoso, guardarlo
3. En siguiente llamada, probar cacheado primero

**Verificación:**
```python
# Ejecutar mismo trámite 2 veces, segunda debe ser más rápida
python main.py --tramite curp --curp XXXX
python main.py --tramite curp --curp XXXX  # ~0.5s más rápido
```

#### 3.5 Caché de resultados OCR por hash de imagen
**Impacto:** MEDIO (2-5s mejora en retries) | **Esfuerzo:** 0.5 días | **Riesgo:** BAJO

**Problema:** `extract_from_image()` no cachea resultados.

**Acciones:**
1. En OCRExtractor, agregar `dict` cacheado: `hash(image_bytes) -> result`
2. Si mismo captcha se reintenta, retornar resultado cacheado

**Verificación:**
```python
# Procesar misma imagen 2 veces, segunda debe ser instantánea
```

#### 3.6 Reducir DPI de pdf2image de 300 a 150
**Impacto:** MEDIO (5-15s mejora por PDF) | **Esfuerzo:** 0.5 días | **Riesgo:** BAJO

**Problema:** `convert_from_path(pdf_path, dpi=300)` es excesivo para texto impreso.

**Acciones:**
1. En ocr.py línea 107, cambiar `dpi=300` a `dpi=150`
2. Verificar que OCR sigue funcionando con calidad aceptable

**Verificación:**
```python
# Procesar PDF con ambos DPI, comparar calidad OCR
```

#### 3.7 Eliminar modelos .pt innecesarios
**Impacto:** BAJO (80 MB disco) | **Esfuerzo:** 0.5 días | **Riesgo:** BAJO

**Problema:** 9 archivos .pt en disco, solo se usan 3.

**Acciones:**
1. Conservar solo `attention_s42_409_v4.pt`, `attention_s123_409_v4.pt`, y ONNX exportado
2. Eliminar los 6 archivos restantes
3. Actualizar documentación

**Verificación:**
```bash
ls captcha_solver_imss/cnn_solver/models/*.pt  # Solo 2-3 archivos
du -sh captcha_solver_imss/cnn_solver/models/  # ~20 MB en vez de 109 MB
```

#### 3.8 Rate limiter por dominio
**Impacto:** MEDIO (2-4s mejora en multi-portal) | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** `_last_request_time` global aplica delay entre portales diferentes.

**Acciones:**
1. Cambiar a `defaultdict(float)` indexado por `urlparse(url).netloc`
2. Permite concurrencia entre portales

**Verificación:**
```python
# Ejecutar CURP + NSS en paralelo, no deben bloquearse entre sí
```

#### 3.9 Reducir wait_for_timeout(2000) a detección inteligente
**Impacto:** MEDIO (1-2s mejora por navegación) | **Esfuerzo:** 1 día | **Riesgo:** MEDIO

**Problema:** Wait fijo de 2s después de cada navegación.

**Acciones:**
1. Reemplazar por `page.wait_for_selector()` del primer elemento clave
2. O reducir a 500ms para portales rápidos

**Verificación:**
```python
# Ejecutar trámite, verificar que no hay waits innecesarios
```

#### 3.10 Paralelizar ensemble de modelos CNN
**Impacto:** BAJO (2x mejora en inference) | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** Ensemble itera modelos secuencialmente.

**Acciones:**
1. Usar `concurrent.futures.ThreadPoolExecutor` para 3 modelos en paralelo
2. Cada modelo es independiente

**Verificación:**
```python
# Benchmark de inference antes/después
```

---

### FASE 4: ARQUITECTURA (1-2 semanas)

#### 4.1 Extraer browser lifecycle a context manager
**Impacto:** MEDIO-ALTO | **Esfuerzo:** 2-3h | **Riesgo:** BAJO

**Problema:** Boilerplate de browser lifecycle duplicado 13 veces (~130 líneas).

**Acciones:**
1. Crear `async with self.browser_context() as page:` en BaseModule
2. Encapsular launch/try/finally/close
3. Eliminar boilerplate de 13 módulos

**Verificación:**
```bash
grep -c "launch_browser" src/modules/*.py  # Debe ser 1 (solo en base.py)
```

#### 4.2 Reemplazar input() bloqueante con callback de interacción
**Impacto:** ALTO | **Esfuerzo:** 6-8h | **Riesgo:** ALTO

**Problema:** 7 llamadas a `input()` bloqueante en métodos async rompen API REST y Streamlit.

**Acciones:**
1. Definir `InteractionHandler` abstracto con `async def prompt(message) -> str`
2. Implementar:
   - `CLIPrompt` (usa `input()`)
   - `APIPrompt` (usa queue/websocket con timeout)
   - `TimeoutPrompt` (raise exception tras N segundos)
3. Inyectar via constructor de BaseModule

**Verificación:**
```python
# Ejecutar módulo via API REST sin timeouts
curl -X POST http://localhost:8000/tramite/cita_ine -d '{"curp": "XXXX"}'
```

#### 4.3 Eliminar OCR_AVAILABLE duplicado
**Impacto:** BAJO | **Esfuerzo:** 30min | **Riesgo:** BAJO

**Problema:** Patrón duplicado en curp.py:27-30, nss.py:30-33, antecedentes.py:28-31, tenencia.py:30-33.

**Acciones:**
1. BaseModule ya resuelve esto en `__init__()` líneas 62-68
2. Los 4 módulos deberían usar `self.ocr is not None`

**Verificación:**
```bash
grep -r "OCR_AVAILABLE" src/modules/  # Debe estar vacío
```

#### 4.4 Unificar logging
**Impacto:** MEDIO | **Esfuerzo:** 1h | **Riesgo:** BAJO

**Problema:** Mezcla de `print()` y `self.log()` en módulos.

**Acciones:**
1. Reemplazar todos los `print()` en módulos por `self.log()`/`self.debug()`
2. Especialmente curp.py (15 prints) y tenencia.py (12 prints)

**Verificación:**
```bash
grep -c "print(" src/modules/*.py  # Debe ser 0 o muy bajo
```

---

### FASE 5: TESTING (1-2 semanas)

#### 5.1 Eliminar/migrar tests legacy
**Impacto:** ALTO | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** 8 archivos en raíz no son pytest, no se ejecutan en CI.

**Acciones:**
1. Migrar tests útiles a `tests/` con pytest
2. Eliminar scripts manuales y `debug_*.py`
3. Eliminar `test_curp_vivo.py` (test contra portal real, frágil)

**Verificación:**
```bash
ls test_*.py  # Debe estar vacío
pytest tests/ -v  # Todos los tests pasan
```

#### 5.2 Agregar tests de integración smoke
**Impacto:** ALTO | **Esfuerzo:** 2 días | **Riesgo:** MEDIO

**Problema:** No hay tests contra portales reales, selectores pueden estar rotos.

**Acciones:**
1. Crear `tests/integration/test_portales_smoke.py`
2. Tests headless que verifican: portal accesible, formulario visible, selectores funcionan
3. Marcar como `@pytest.mark.integration` (skip en CI, manual en dev)

**Verificación:**
```bash
pytest tests/integration/ -m integration -v  # Tests de integración pasan
```

#### 5.3 Configurar mypy en CI
**Impacto:** MEDIO | **Esfuerzo:** 0.5 días | **Riesgo:** BAJO

**Problema:** Type hints existen pero no se validan.

**Acciones:**
1. Crear `mypy.ini` con config básica
2. Agregar `mypy src/` a CI pipeline
3. Corregir type errors encontrados

**Verificación:**
```bash
mypy src/  # Sin errores
```

#### 5.4 Agregar tests para utils faltantes
**Impacto:** MEDIO | **Esfuerzo:** 1 día | **Riesgo:** BAJO

**Problema:** utils/claude.py, utils/pii.py, utils/voice_input.py sin tests.

**Acciones:**
1. Crear tests/test_claude.py, tests/test_pii.py
2. Mock APIs externas (Claude API)

**Verificación:**
```bash
pytest tests/test_pii.py tests/test_claude.py -v  # Tests pasan
```

#### 5.5 Agregar security scanning
**Impacto:** MEDIO | **Esfuerzo:** 0.5 días | **Riesgo:** BAJO

**Problema:** No hay detección de secrets o vulnerabilidades.

**Acciones:**
1. Agregar `bandit -r src/` a CI
2. Agregar `safety check` para dependencias

**Verificación:**
```bash
bandit -r src/  # Sin vulnerabilidades críticas
safety check  # Dependencias seguras
```

#### 5.6 Coverage threshold en CI
**Impacto:** MEDIO | **Esfuerzo:** 0.2 días | **Riesgo:** BAJO

**Problema:** Coverage se reporta pero no hay mínimo requerido.

**Acciones:**
1. Agregar `--cov-fail-under=80` a pytest en CI

**Verificación:**
```bash
pytest tests/ --cov=src --cov-fail-under=80  # Cobertura >= 80%
```

---

### FASE 6: ACTUALIZACIÓN PLAYWRIGHT (Opcional — 1 semana)

#### 6.1 Actualizar a Playwright 1.61
**Impacto:** MEDIO | **Esfuerzo:** 1-2 días | **Riesgo:** MEDIO

**Nuevas APIs útiles:**
- **WebAuthn passkeys** (1.61): Para portales que usan passkeys
- **Web Storage API** (1.61): `page.local_storage` para leer/escribir storage
- **Screencast API** (1.59): Para grabar videos de trámites (debug/auditoría)
- **Aria snapshots** (1.49): Para snapshot testing de accesibilidad

**Acciones:**
1. Actualizar requirements.txt: `playwright>=1.61.0,<2.0`
2. Ejecutar `playwright install` para actualizar browsers
3. Probar que todos los tests pasan
4. Considerar usar Screencast API para grabar trámites (debug)

**Verificación:**
```bash
pip install -U playwright
playwright install
pytest tests/ -v  # Todos los tests pasan
```

---

## 📋 Checklist de Verificación Final

### Seguridad
- [ ] config.env NO trackeado en git
- [ ] Secrets en Windows Credential Manager
- [ ] Passwords hasheados con bcrypt/argon2
- [ ] Salt único por instancia para STORAGE_KEY
- [ ] Sin except Exception: pass silenciosos
- [ ] No se muestran API keys en stdout/logs
- [ ] Validación de inputs en todos los módulos
- [ ] Logs sin datos sensibles (sanitización PII)

### Rendimiento
- [ ] Browser pool implementado (2-3 browsers)
- [ ] Lazy imports para torch/easyocr/whisper
- [ ] time.sleep() reemplazado por await asyncio.sleep()
- [ ] Caché de selectores CSS
- [ ] Caché de resultados OCR
- [ ] DPI de pdf2image reducido a 150
- [ ] Modelos .pt innecesarios eliminados
- [ ] Rate limiter por dominio
- [ ] wait_for_timeout() optimizado

### Arquitectura
- [ ] Sin archivos .py duplicados en raíz
- [ ] Sin sys.path.insert hacks
- [ ] Browser lifecycle en context manager
- [ ] input() reemplazado por InteractionHandler
- [ ] OCR_AVAILABLE unificado en BaseModule
- [ ] Logging unificado (sin print())

### Testing
- [ ] Tests legacy eliminados/migrados
- [ ] Tests de integración smoke contra portales reales
- [ ] mypy configurado y pasando en CI
- [ ] Tests para utils faltantes (claude, pii, voice_input)
- [ ] Security scanning en CI (bandit, safety)
- [ ] Coverage threshold >= 80% en CI

### Documentación
- [ ] README.md actualizado con nueva estructura
- [ ] ROADMAP_COMPLETO.md actualizado con progreso
- [ ] pyproject.toml con entry points correctos
- [ ] .editorconfig con charset = utf-8

---

## 🎯 Cronograma Estimado

| Fase | Duración | Dependencias |
|------|----------|--------------|
| F1: Higiene del repo | 1 semana | — |
| F2: Seguridad crítica | 1 semana | F1 |
| F3: Rendimiento | 1-2 semanas | F1 |
| F4: Arquitectura | 1-2 semanas | F1, F2 |
| F5: Testing | 1-2 semanas | F1 |
| F6: Playwright update | 1 semana | F1 (opcional) |

**Total estimado:** 6-9 semanas para implementación completa

**Prioridad inmediata (esta sesión):**
1. F1.1: Consolidar estructura de archivos
2. F1.2: Resolver empaquetado Python
3. F2.1: Migrar secrets a Windows Credential Manager
4. F3.2: Lazy imports para torch/easyocr/whisper

---

## 📊 Métricas de Éxito

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Score general | 7.0/10 | 8.5-9.0/10 |
| Tests totales | 394 | 450+ |
| Cobertura | 78% | 85%+ |
| Tiempo startup | ~15s | <5s |
| Tiempo CURP | 16s | <12s |
| Tiempo NSS | 30-60s | <25s |
| Archivos .py raíz | 22 | 2 (app.py, main.py) |
| sys.path.insert | 33 | 0 |
| Vulnerabilidades críticas | 3 | 0 |
| input() bloqueantes | 7 | 0 |

---

## 🔗 Recursos Adicionacionales

- **Playwright 1.61 Release Notes**: https://playwright.dev/python/docs/release-notes
- **WebAuthn Passkeys**: https://playwright.dev/python/docs/api/class-credentials
- **Screencast API**: https://playwright.dev/python/docs/api/class-page#page-screencast
- **Aria Snapshots**: https://playwright.dev/python/docs/aria-snapshots

---

## 📝 Notas Finales

Este plan fue generado mediante análisis multi-agente:
- **Agente 1 (Arquitectura)**: Análisis de estructura, patrones, deuda técnica
- **Agente 2 (Seguridad/Rendimiento)**: Vulnerabilidades, cuellos de botella, recursos
- **Agente 3 (Testing/Calidad)**: Cobertura, calidad de tests, CI/CD
- **Web Research**: Playwright 2026, mejores prácticas, nuevas APIs

**Recomendación:** Implementar F1 y F2 primero (higiene + seguridad), luego F3 (rendimiento), y finalmente F4-F6 (arquitectura, testing, actualizaciones).

**Score proyectado post-implementación:** 8.5-9.0/10
