# Audit Round 2 — Hallazgos y Correcciones

**Fecha**: 2026-06-24
**Auditores**: 3 subagentes (Code Quality, Security, Architecture)
**Re-verificadores**: 3 subagentes

## Correcciones Aplicadas (11 fixes)

### Críticas
1. **api.py:166,181** — Fuga de errores internos a clientes API. Ahora logea server-side y retorna msg genérico.
2. **base.py:96-102,135,158,241,262** — Silent error swallowing en close_browser, fill_field, click_first, wait_for_recaptcha, detect_site_key. Todos loguean con self.debug() ahora.
3. **base.py:121-122** — RuntimeError reemplazado por ModuleError para consistencia con jerarquía de excepciones.

### Seguridad
4. **base.py:209** — CAPTCHA_VALUE solo se usa si DEBUG=true.
5. **nss.py:303** — CAPTCHA_VALUE solo se usa si DEBUG=true.
6. **Dockerfile** — Se agregó USER 1000 (non-root).
7. **.dockerignore** — Creado con exclusiones de secrets, logs, output, __pycache__, etc.

### Performance
8. **base.py:188-195** — requests.get() síncrono envuelto en loop.run_in_executor() para no bloquear event loop.
9. **nss.py:256** — Mismo fix que #8 en módulo NSS.

### Mantenibilidad
10. **ocr.py:64,84** — PIL Image.open() ahora usa context manager (with).
11. **curp.py:105** — Debug screenshot usa OUTPUT_DIR en vez de hardcode.

## Correcciones en tests (3 tests)
- test_base.py: test_solver_fails_env_var_fallback → mock específico para DEBUG gate
- test_base.py: test_open_pdf_* → HEADLESS mock
- test_logger.py: test_error_logs → exc_info param

## Issues Verificados como Falsos Positivos
- **antecedentes.py:244-257** — Password hashing NO es bug: save_profile pasa por storage._hash_sensitive() que PBKDF2-hashes antes de escribir al store encriptado con Fernet.

## Score Estimado Post-Fixes
- Seguridad: 5.5 → 7.0/10
- Arquitectura: 5.0 → 6.0/10
- Tests: 7.0 → 8.0/10
- Overall: ~5.5 → ~7.0/10 (+1.5 pts)

## Issues Remanentes (Design-level, requieren decisión)
1. BaseModule god object (~400 líneas, múltiples responsabilidades)
2. Rate limiting global mutable (module-level en base.py)
3. Triple entry point redundancy (main.py, main_multimodal.py, orchestrator.py)
4. sys.path.insert en main.py y api.py
5. ~30 mypy warnings pre-existentes
