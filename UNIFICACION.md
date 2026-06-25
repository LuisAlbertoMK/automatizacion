# Plan de Unificación — automatizacion + tramites-auto

**Fecha**: 2026-06-25
**Objetivo**: Unificar los dos repos que hacen lo mismo (automatización de trámites GOB.MX) en uno solo.

## Diagnóstico

| Proyecto | Stack | Trámites | Estado |
|----------|-------|----------|--------|
| `automatizacion` (Python) | Python + Playwright Firefox | 4 (CURP, NSS, Antecedentes, Tenencia) | ✅ Activo, infraestructura completa |
| `tramites-auto` (Node.js) | Node.js + Playwright Chromium | 13 + docs IA | 💀 1 commit, archivado |

**Decisión**: `automatizacion` (Python) es el repo canónico. Migrar los 9 trámites extra de `tramites-auto`.

## Trámites a migrar

| # | Trámite | Portal | Captcha | Prioridad | Módulo destino |
|---|---------|--------|---------|-----------|----------------|
| 1 | RFC SAT | sat.gob.mx | Sí | 🔴 Alta | `src/modules/rfc.py` |
| 2 | Acta Nacimiento | gob.mx/actas | Sí | 🔴 Alta | `src/modules/acta_nacimiento.py` |
| 3 | Cita Pasaporte SRE | gob.mx (SRE230) | Sí | 🔴 Alta | `src/modules/pasaporte.py` |
| 4 | Semanas Cotizadas IMSS | IMSS | No | 🟡 Media | `src/modules/semanas.py` |
| 5 | Control de Confianza | SESNSP | No | 🟡 Media | `src/modules/control_confianza.py` |
| 6 | Buró de Crédito | burodecredito.com.mx | Sí | 🟡 Media | `src/modules/buro.py` |
| 7 | Círculo de Crédito | circulodecredito.com.mx | Sí | 🟡 Media | `src/modules/circulo.py` |
| 8 | Cita INE | ine.mx | Sí | 🟡 Media | `src/modules/cita_ine.py` |
| 9 | Cita SAT | citas.sat.gob.mx | Sí | 🟡 Media | `src/modules/cita_sat.py` |

## Documentos a migrar

| Documento | Stack origen | Stack destino | Prioridad |
|-----------|-------------|---------------|-----------|
| CV profesional | Node.js + `docx` | Python + `python-docx` | 🟢 Baja |
| Escritos/cartas/contratos | Node.js + `docx` + Claude API | Python + `python-docx` | 🟢 Baja |

## Archivos a modificar en automatizacion

- `src/exceptions.py` — Agregar excepciones para cada nuevo módulo
- `src/modules/__init__.py` — Sin cambios (vacío)
- `src/modules/orchestrator.py` — Registrar 9 nuevos módulos
- `src/main.py` — Agregar comandos CLI para nuevos trámites
- `src/modules/*.py` — 9 nuevos módulos (ver sección de migración)
- `pyproject.toml` — Agregar `python-docx` como dependencia opcional
- `README.md` — Actualizar tabla de trámites

## Archivos a archivar de tramites-auto

- `D:\tramites-auto` completo (respaldo antes de borrar)

## Proceso de migración por módulo

Cada módulo nuevo sigue el patrón `BaseModule`:

```python
class XModule(BaseModule):
    async def consultar(self, **kwargs) -> dict:
        """Punto de entrada: lanza browser, ejecuta flujo, retorna resultado."""
    
    async def _run(self, page, **kwargs) -> dict:
        """Flujo: navegar → llenar formulario → captcha → submit → extraer resultado."""
```

- Usa `self.goto()` con fallback
- Usa `self.fill_field()` y `self.click_first()` con múltiples selectores
- Usa `self.resolve_image_captcha()` para captcha de imagen
- Usa `self.wait_for_recaptcha()` para reCAPTCHA
- Usa `self.download_pdf()` para descargar PDFs

## Post-migración

- [ ] Verificar que todos los módulos importan correctamente
- [ ] Ejecutar `python health_check.py`
- [ ] Ejecutar tests existentes
- [ ] Actualizar ROADMAP_COMPLETO.md
- [ ] Archivar `D:\tramites-auto`

## Riesgos

| Riesgo | Probabilidad | Mitigación |
|--------|-------------|------------|
| Selectores CSS cambiaron | Alta | Usar múltiples selectores estilo `fill_field()` |
| Portal caído | Media | `self.goto()` con fallback ya implementado |
| reCAPTCHA no resuelto | Media | `wait_for_recaptcha()` con timeout configurable |
| Módulo sin probar | Media | Los tests se agregarán después de la migración |
