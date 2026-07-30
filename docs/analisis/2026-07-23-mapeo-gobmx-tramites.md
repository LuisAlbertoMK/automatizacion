# Mapeo gob.mx — Trámites Cubiertos vs Oportunidades

**Fecha:** 2026-07-23  
**Objetivo:** Cruzar catálogo oficial de gob.mx con los módulos existentes del proyecto para identificar cobertura real y nuevas oportunidades.

---

## Fuentes de datos

- Catálogo Nacional de Trámites (datos-publicos.mx) — 103,755 registros federales
- gob.mx/tramites — portal único (protegido por Cloudflare)
- Programa de Simplificación de Trámites 2026 (ATDT) — 5,594 trámites federales, 3,497 simplificados, 1,711 eliminados
- README.md y orchestrator.py del proyecto

---

## Módulos existentes en el proyecto (14)

| # | Trámite | Portal oficial | Módulo | Estado proyecto | Funcional |
|---|---------|---------------|--------|-----------------|-----------|
| 1 | CURP (consulta + PDF) | gob.mx/curp | `curp.py` | ✅ Producción | 🟢 Sí — Playwright + OCR captcha |
| 2 | NSS IMSS | imss.gob.mx | `nss.py` | ✅ Producción | 🟢 Sí — free captcha solver |
| 3 | RFC SAT | sat.gob.mx | `rfc.py` | ⚙️ Migrado | 🟡 Verificar |
| 4 | Acta de Nacimiento | Registro Civil (varía x estado) | `acta_nacimiento.py` | ⚙️ Migrado | 🟡 Verificar — 32 estados |
| 5 | Cita Pasaporte SRE | citas.sre.gob.mx | `pasaporte.py` | ⚙️ Migrado | 🟡 Verificar |
| 6 | Semanas Cotizadas IMSS | imss.gob.mx | `semanas.py` | ⚙️ Migrado | 🟡 Verificar |
| 7 | Antecedentes No Penales | SEGOB / estatal | `antecedentes.py` | 🔶 Escrito | 🟠 Solo lógica, sin Playwright |
| 8 | Tenencia Vehicular | Estatal (varía) | `tenencia.py` | 🔶 Escrito | 🟠 Solo lógica, sin Playwright |
| 9 | Control de Confianza | sesnsp.gob.mx | `control_confianza.py` | ⚙️ Migrado | 🟡 Verificar |
| 10 | Buró de Crédito | burondecredito.com.mx | `buro.py` | ⚙️ Migrado | 🟡 Verificar |
| 11 | Círculo de Crédito | circulondecredito.com.mx | `circulo.py` | ⚙️ Migrado | 🟡 Verificar |
| 12 | Cita INE | citas.ine.mx | `cita_ine.py` | ⚙️ Migrado | 🟡 Verificar |
| 13 | Cita SAT | sat.gob.mx | `cita_sat.py` | ⚙️ Migrado | 🟡 Verificar |
| 14 | Constancia Situación Fiscal | sat.gob.mx | (¿en rfc.py?) | — | 🔴 Verificar |

### Resumen de estados

```
Producción (funcional):   2/14  (14%)
Migrados (sin verificar): 9/14  (64%)
Escritos (sin Playwright): 2/14  (14%)
Sin módulo:               1/14  (7%)
```

---

## Trámites TOP en gob.mx que NO están en el proyecto

| # | Trámite | Portal | Demanda | Complejidad | Prioridad nueva |
|---|---------|--------|---------|-------------|-----------------|
| 1 | Constancia de Situación Fiscal | sat.gob.mx | 🔥 Top 5 | Baja (CURP + contraseña) | **ALTA** |
| 2 | e.firma / Contraseña SAT | sat.gob.mx | 🔥 Alta | Media | **ALTA** |
| 3 | Opinión de Cumplimiento (32-D) | sat.gob.mx | 🔥 Alta | Baja (descarga directa) | **ALTA** |
| 4 | Lista Nominal INE | ine.mx | Alta | Baja (CURP) | MEDIA |
| 5 | Cédula Profesional | cedula.profeco.gob.mx | Alta | Baja (nombre) | MEDIA |
| 6 | Constancia Vigencia Derechos IMSS | imss.gob.mx | Alta | Baja (NSS) | MEDIA |
| 7 | Alta Patronal IMSS | idse.imss.gob.mx | Media | Alta (formulario largo) | BAJA |
| 8 | Apostilla de Documentos | gob.mx/sre | Media | Alta (presencial) | BAJA |
| 9 | Visa Americana B1/B2 | ceac.state.gov | Alta | Imposible (consular) | ❌ |

---

## Top 3 Trámites más populares en gob.mx (según simplificación 2026)

1. **CURP** — gob.mx/curp — GRATUITO — ✅ Ya tenemos
2. **Acta de Nacimiento** — miregistrocivil.gob.mx — Gratis-$98 — ⚙️ Migrado
3. **Pasaporte** — gob.mx/pasaporte — Desde $86 — ⚙️ Migrado
4. **Semanas Cotizadas IMSS** — imss.gob.mx — GRATUITO — ⚙️ Migrado
5. **Constancia de Situación Fiscal** — sat.gob.mx — $420 — 🔴 NO tenemos

---

## Recomendación

### Fase 1: Verificar lo que ya existe (1-2 días)
Probar CURP y NSS contra portales reales. Si funcionan, probar los 9 migrados.
Razón: No tiene sentido construir nuevos módulos si los existentes están rotos.

### Fase 2: Constancia de Situación Fiscal (1 día)
Es el trámite #5 en demanda, #1 que falta. sat.gob.mx lo ofrece en línea.
Requiere: CURP + contraseña SAT (o e.firma). Mismo patrón que CURP.

### Fase 3: Constancia Vigencia Derechos IMSS (medio día)
Extensión natural del módulo NSS existente.

### No priorizar
- Visa americana (imposible automatizar — es consular)
- Alta patronal IMSS (formulario muy largo, baja demanda ciudadana)
- Apostilla (requiere presencial)

---

## Notas técnicas

- **Cloudflare**: gob.mx tiene protección challenge — no se puede scrapear con requests. Necesita Playwright con browser real.
- **CAPTCHAs**: Los portales del SAT usan reCAPTCHA v2/v3. Los de IMSS usan captcha de imagen. RENAPO usa captcha numérico.
- **Simplificación 2026**: El gobierno está reduciendo requisitos (de 6 a 2 promedio) y eliminando trámites. Algunos portales pueden cambiar URLs o flujos.
- **LlaveMX**: 28 millones de cuentas, 242 sistemas integrados. Futura plataforma única — posible punto de integración.
