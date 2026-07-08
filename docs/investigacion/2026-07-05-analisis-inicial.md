# Análisis Inicial — agente-tramites-gobmx v1.0.0

**Fecha**: 2026-07-05 · **Score**: 8.0/10
**Rama**: `master` · **Cambios**: solo docs/investigacion/_data.json (untracked)

---

## Resumen

Automatización de trámites gubernamentales mexicanos vía Playwright + Firefox.
CURP, NSS IMSS, RFC SAT, Acta de Nacimiento, Cita Pasaporte, y más.
**399 tests**, captcha solving multi-tier (CNN → OCR → Whisper → 2captcha → manual).
Reduce trámites de 10-25 min a <2 min.

---

## Arquitectura

```
src/
├── main.py              → CLI entry point (681 lines)
├── api.py               → FastAPI REST server
├── exceptions.py        → Jerarquía unificada de errores
├── modules/             → 14 módulos de trámites + base.py + orchestrator.py
│   ├── base.py          → BaseModule: browser lifecycle, captcha, PDF, rate limiting
│   ├── curp.py, nss.py, rfc.py, acta_nacimiento.py, pasaporte.py
│   ├── antecedentes.py, tenencia.py, semanas.py
│   ├── control_confianza.py, buro.py, circulo.py, credito.py
│   ├── cita_ine.py, cita_sat.py
│   └── orchestrator.py  → Orquestador multimodal (481 lines)
├── utils/               → captcha, logger, pii, storage, secrets, mail_reader, voice
└── captcha_solver_imss/ → CNN + EasyOCR + Tesseract ensemble

tests/ → 15 archivos, 399 tests
```

### Captcha Solving (3-tier)
1. **CNN** (~2ms) para IMSS — ensemble dedicado en `captcha_solver_imss/`
2. **Free**: Tesseract OCR + Whisper (reCAPTCHA v2 audio)
3. **Paid**: 2captcha.com (image ~$0.001, reCAPTCHA ~$0.002)

---

## Hallazgos Clave

### ✅ Fortalezas
- 399 tests (cobertura 31% → 61% en un commit)
- Manejo de errores robusto: 3-tier fallback en captchas, try/finally en browser lifecycle
- PII sanitization automática en logs (CURP/NSS/email)
- Perfiles encriptados con Fernet + PBKDF2 (600K iteraciones)
- Documentación extensa en español (ROADMAP, GUIA_COMPLETA, ANALISIS, BITACORA)
- Ruff linting + CI en 3 versiones de Python

### ⚠️ Debilidades
- ~20 screenshots .PNG en root (debug artifacts, ~1.5MB)
- Test files huérfanos en root (test_curp_simple.py, etc.)
- `app.py` (Streamlit) en root — entry point dual no documentado
- requirements.txt duplica pyproject.toml
- Captcha CNN solver: estado del pipeline de training incierto
- Sin tests para captcha_solver_imss/, free_captcha.py, voice_input.py

### 🔮 Recomendaciones
1. Mover screenshots a directorio temporal y .gitignore
2. Eliminar test files huérfanos del root
3. Unificar pyproject.toml como source of truth de dependencias
4. Estandarizar lazy imports en todos los módulos

---

## Scoring

| Dimensión | Rating | Nota |
|-----------|--------|------|
| Arquitectura | 7/10 | BaseModule sólido, entry points duplicados |
| Código | 7/10 | Tipado parcial, módulos repetitivos |
| Tests | 7/10 | 399 tests, 61% coverage, gaps en captcha solver |
| Documentación | 8/10 | Extensa en español, roadmap claro |
| Git salud | 8/10 | Conventional commits, CI matrix, branch simple |
| Seguridad | 8/10 | PII sanitization, Fernet, PBKDF2, keyring |
| **Overall** | **7.5/10** | Proyecto funcional con calidad sólida; necesita housekeeping |
