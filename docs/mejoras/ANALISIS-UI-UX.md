# Análisis de UI/UX y Frontend

**Proyecto:** agente-tramites-gobmx  
**Fecha:** 2026-07-08  
**Analista:** Señor Arquitecto (subagente especializado)

---

## Problemas Críticos de UX

### 🔴 UX1 — Sin directorio `.streamlit/` — sin theming ni configuración

No existe `.streamlit/config.toml`. Esto significa:
- Sin tema personalizado (default Streamlit con acento rojo)
- Sin configuración de server/session
- Sin custom CSS

### 🔴 UX2 — `st.rerun()` sin condiciones — loops infinitos potenciales

**Archivo:** `app.py:191,208`

```python
st.rerun()  # Sin verificación de necesidad
```

Streamlit ya rerunea al cambiar widgets. Forzar rerun puede causar loops.

### 🔴 UX3 — Sin loading states diferenciados en operaciones largas

Para CURP (~16s) y NSS (~30-60s) solo usan `st.spinner()` estático:
- Sin progress bar real
- Sin botón de cancelación
- Sin tiempo transcurrido
- Sin fallback si el spinner se traba

### 🔴 UX4 — `except Exception` genérico — 14 tipos de error ignorados

```python
except Exception as e:
    st.error(f"Error: {e}")
```

`CaptchaError`, `StorageError`, `CURPError` — todos al mismo mensaje genérico.

### 🔴 UX5 — Botones de acceso rápido en Dashboard no funcionan

```python
st.switch_page("app.py")       # No funciona fuera de multipage
st.session_state["page"] = "curp"  # Sin efecto porque routing usa radio
```

### 🔴 UX6 — Sin `session_state` management

No hay:
- Perfil activo entre secciones
- Cache de resultados
- Historial de consultas
- Persistencia de inputs

---

## Mejoras de Usabilidad Priorizadas

### 🟡 Alta Prioridad

| ID | Mejora | Esfuerzo |
|----|--------|----------|
| U1 | Crear `.streamlit/config.toml` con tema personalizado | 0.5 día |
| U2 | Refactorizar routing con `session_state` sincronizado | 0.5 día |
| U3 | Manejo de errores específicos con sugerencias de acción | 1 día |
| U4 | Agregar `@st.cache_data` para datos que no cambian frecuentemente | 0.5 día |
| U5 | Validación inline de CURP (sin esperar submit) | 0.5 día |
| U6 | Remplazar `st.rerun()` condicional | 0.5 día |
| U7 | Sistema de progreso para operaciones largas (30-60s) | 1 día |

### 🟡 Media Prioridad

| ID | Mejora |
|----|--------|
| U8 | Búsqueda en perfiles |
| U9 | Edición de perfiles existentes |
| U10 | Botón de cancelación en operaciones async |
| U11 | Visualización de historial de sesión |
| U12 | Homogeneizar sanitización usando `src/utils/pii.py` |
| U13 | Dashboard con métricas y delta vs período anterior |

### 🟢 Baja Prioridad

| ID | Mejora |
|----|--------|
| U14 | Sistema de notificaciones persistente con session_state |
| U15 | Internacionalización (estructura preparada) |
| U16 | Modo offline/fallback states |
| U17 | Accesibilidad básica WCAG |

---

## Puntaje por Categoría

| Categoría | Nota | Comentario |
|-----------|------|------------|
| UX general | ⭐⭐ | Funcional pero frágil. Sin feedback de estado |
| Streamlit patterns | ⭐⭐ | Sin session_state, sin cache, rerun sin control |
| Accesibilidad | ⭐ | Sin CSS, sin tema, sin ARIA |
| Error handling UI | ⭐ | except Exception genérico. 14 excepciones ignoradas |
| Loading states | ⭐⭐ | Solo spinner básico. Sin progress ni cancelación |
| Input validation | ⭐⭐ | CURP validada solo al submit |
| Seguridad UI | ⭐⭐⭐⭐⭐ | Encriptación Fernet, sanitización, masking |
| Perfiles UX | ⭐⭐ | Sin búsqueda, sin edición, sin paginación |

**Puntaje general: 2.3/5** — Funcional pero con fricción. Prioridades: routing con session_state, errores específicos, cache.
