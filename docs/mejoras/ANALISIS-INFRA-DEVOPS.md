# Análisis de Infraestructura, DevOps y Documentación

**Proyecto:** agente-tramites-gobmx  
**Fecha:** 2026-07-08  
**Analista:** Señor Arquitecto (subagente especializado)

---

## Dockerfile

### ✅ Fortalezas
- Multi-stage build
- Non-root user (uid 1000)
- HEALTHCHECK
- `--no-install-recommends` en apt
- `--no-cache-dir` en pip (builder)

### 🔴 Problemas

| # | Problema | Gravedad |
|---|----------|----------|
| 1 | `ENTRYPOINT ["python", "main.py"]` — apunta a shim legacy que puede desaparecer | 🔴 Crítico |
| 2 | Imagen estimada ~2-3 GB (torch, easyocr, whisper, firefox) | 🔴 Crítico |
| 3 | `pip install -e .` en runtime (editable mode innecesario) | 🟡 Alto |
| 4 | Sin `--no-cache-dir` en runtime stage | 🟡 Medio |
| 5 | Sin `RUN --mount=type=cache` para pip (BuildKit) | 🟡 Medio |
| 6 | Sin etiquetas LABEL | 🟡 Bajo |
| 7 | Sin ARG para versión de Playwright | 🟡 Bajo |

---

## Docker Compose

### ✅ Fortalezas
- Profiles correctos (app, api como opcionales)
- Volúmenes para datos persistentes

### 🔴 Problemas

| # | Problema | Gravedad |
|---|----------|----------|
| 1 | `version: "3.9"` obsoleto en Docker Compose V2 | 🟡 Medio |
| 2 | Sin restart policy en servicios larga duración | 🟡 Alto |
| 3 | Sin HEALTHCHECK en compose level | 🟡 Medio |
| 4 | Sin named volumes para cache de Playwright | 🟡 Medio |
| 5 | Sin `depends_on` para orden de arranque | 🟡 Bajo |
| 6 | Streamlit y API sirven HTTP plano sin TLS | 🟡 Alto |
| 7 | Mínimo privilegio violado: todos los servicios montan config.env completo | 🟡 Medio |
| 8 | Sin tmpfs para archivos temporales sensibles | 🟡 Medio |

---

## CI/CD (GitHub Actions — ci.yml)

### ✅ Fortalezas
- Matriz Python 3.11/3.12/3.13
- Ruff linting + compileall
- pytest con coverage + Codecov
- Docker build en master
- Uso de uv para instalación rápida

### 🔴 Problemas

| # | Problema | Gravedad |
|---|----------|----------|
| 1 | Sin deploy automático (ni registry push, ni entorno) | 🔴 Crítico |
| 2 | Secrets hardcodeados en YAML | 🔴 Crítico |
| 3 | Sin security scanning (bandit, safety, trivy, semgrep) | 🔴 Alto |
| 4 | Sin type checking (mypy no se ejecuta) | 🔴 Alto |
| 5 | Sin tests de integración | 🔴 Alto |
| 6 | Docker tag siempre `:latest` (sin SHA, sin semver) | 🟡 Alto |
| 7 | Docker build sin cache-from | 🟡 Medio |
| 8 | Sin badge de CI en README | 🟡 Bajo |

---

## Git Hooks (`.githooks/pre-commit`)

### ✅ Excelente — 5 etapas:
1. Secrets scan (API keys, tokens, private keys)
2. Debug statements (pdb, breakpoint)
3. Large files (>1MB)
4. Ruff linting sobre staged content
5. Quick pytest sobre archivos Python modificados

### 🔴 Mejorable

| # | Problema | Gravedad |
|---|----------|----------|
| 1 | No se menciona en README (developer nuevo no sabe que existe) | 🟡 Alto |
| 2 | No hay script de instalación automática (`git config core.hooksPath`) | 🟡 Alto |
| 3 | Sin pre-push hook para tests largos | 🟡 Bajo |
| 4 | Compatibilidad Windows (Git Bash) no verificada | 🟡 Bajo |

---

## Documentación

### ✅ Fortalezas
- README con arquitectura visual, tablas, instalación multi-forma
- `docs/` con análisis, investigaciones, operaciones
- Proceso de mejora continua documentado (ciclos P1→P2→P3)
- Score tracking con dimensiones y tendencia

### 🔴 Problemas

| # | Problema | Gravedad |
|---|----------|----------|
| 1 | **13 archivos .md en raíz** que deberían estar en `docs/` | 🔴 Alto |
| 2 | PROJECT-SCORE.md duplicado e inconsistente (raíz 7.0 vs .project.json 8.0) | 🟡 Alto |
| 3 | Sin API docs en markdown (OpenAPI existe pero no documentado) | 🟡 Alto |
| 4 | Sin guía de contribución | 🟡 Medio |
| 5 | Sin troubleshooting/FAQ | 🟡 Medio |
| 6 | Sin ADRs (Architecture Decision Records) | 🟡 Bajo |
| 7 | Variables de entorno no documentadas en README | 🟡 Alto |

---

## Dev Experience

| Aspecto | Estado |
|---------|--------|
| health_check.py | ✅ |
| config.example.env | ✅ |
| Docker + Compose | ✅ |
| tools/ scripts | ✅ (12 scripts) |
| Devcontainer | ❌ |
| .editorconfig | ❌ |
| Makefile / Taskfile | ❌ |
| Pre-commit auto-install | ❌ |
| Lock file (requirements.lock) | ❌ |

---

## Recomendaciones Concretas (Top 5)

### 🔥 Prioridad Inmediata (4-6 horas)

```
1. ENTRYPOINT del Dockerfile → "tramites"
   └── eliminar main.py de raíz si existe

2. Secrets CI → GitHub Secrets
   └── CAPTCHA_API_KEY y STORAGE_KEY

3. Push Docker image a GHCR
   └── tag con SHA + latest

4. Mover 13 .md de raíz a docs/
   └── unificar PROJECT-SCORE.md

5. Agregar security scanning a CI
   └── bandit + safety mínimo
```

### Prioridad Alta (1 semana)

- Docker Compose V2 hygiene (eliminar version, agregar restart, HEALTHCHECK)
- Reducir imagen Docker (separar torch como capa opcional)
- Auto-install de git hooks
- Release workflow con etiquetas

### Prioridad Media (2 semanas)

- Lock file (`uv pip compile`)
- Devcontainer
- CHANGELOG.md automatizado
- API docs desde OpenAPI
- Backup/restore documentado
