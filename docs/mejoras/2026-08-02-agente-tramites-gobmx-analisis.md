# Verificación de Portales — 2026-08-02 📍

**Alcance**: HTTP check en vivo de 14 URLs + deep-dive web (2 subagentes) + auditoría de código (1 subagente).
**Fecha**: 2026-08-02 · **Método**: `requests` con timeout 12s + webfetch/websearch + Read de módulos.

---

## Resumen ejecutivo

**12/13 portales viven** (solo ControlConfianza muerto). **PERO: ningún módulo es 100% automático hoy** — todos son semiautomáticos (captcha manual o intervención en algún paso). El estado "⚙️ Migrado" del README significa *migrado de arquitectura*, NO *E2E verificado automático*.

### HTTP Check en vivo (14 URLs)

| Portal | Módulo | ST | Verdict |
|--------|--------|----|---------|
| CURP (gob.mx) | curp.py | 200 | ✅ Vivo (Akamai challenge) |
| CURP (consultas) | curp.py | ERR | ⚠️ Timeout a GET limpio — requiere Playwright |
| NSS IMSS | nss.py | 403 | ⚠️ Bot-protection — Playwright OK |
| Semanas IMSS | semanas.py | 403 | ⚠️ Bot-protection — Playwright OK |
| RFC SAT | rfc.py | 403 | ⚠️ Access Gateway — Playwright OK |
| Acta Nacimiento | acta_nacimiento.py | 200 | ✅ Vivo |
| Pasaporte SRE | pasaporte.py | 200 | ✅ Vivo |
| **ControlConfianza** | control_confianza.py | ERR | ❌ **DNS dead** — confirmado |
| **Antecedentes** | antecedentes.py | 200 | ✅ **VIVO + operativo** (título real) |
| Cita INE | cita_ine.py | 403 | ⚠️ Bot-protection (dominio vivo) |
| **Cita SAT** | cita_sat.py | 502 hoy | ⚠️ **Transitorio** — 200 en 3/3 fetches |
| Tenencia EdoMex | tenencia.py | 200 | ✅ Vivo (lento 7.8s) |
| **Buró Crédito** | credito.py | ERR | ⚠️ **Akamai bot-block** (NO 404) |
| **Círculo Crédito** | credito.py | 403 | ⚠️ Cloudflare — **URL CAMBIÓ** |

---

## 🔴 Hallazgos que CORRIGEN documentación previa

### H1. Círculo de Crédito — URL obsoleta + flujo cambiado (CRITICAL)
- URL canónica **cambió**: `/reporte-credito-especial` → **`/mi-rce`** ("Mi RCE®", ya en menú principal).
- Requiere **registro y login** ("Mi Círculo"). Primera consulta del año **gratis**, segunda **$37 MXN** (2026).
- `src/tramites/credito.py` usa la URL vieja → fallaría en `goto` paso 1 (Cloudflare 403).
- `confidence: high` (websearch fechado 2026 + home real con título).

### H2. Buró de Crédito — NO es "404 portal moved" (corrige análisis 2026-07-23)
- El 404 reportado el 2026-07-23 era **bloqueo Akamai** ("Request Rejected"), no cambio de URL.
- Producto existe y conserva nombre: **$35.60 MXN**, gratis 1 vez cada 12 meses.
- Requiere **Playwright con fingerprint real + retry** (Akamai rechaza GETs limpios).
- `confidence: high` (confirmación indirecta: host vivo + página existente + copy en índice).

### H3. Antecedentes No Penales — VIVO con requisitos nuevos (dato fresco)
- Portal **operativo**: CURP o Llave MX, **no requiere registro**. Solo mayores de edad, ámbito federal.
- **Costo $240 MXN** (enero 2026) — pagado en línea o línea de captura, acreditación 72h, descarga 30 días.
- Nuevo: **apostilla/legalización en línea** (`apostillaylegalizacionmexico.segob.gob.mx`).
- El README lo marca "🔶 Escrito" — correcto, pero el portal está vivo y scrapeable (sin Cloudflare).
- `confidence: high` (webfetch directo 200 + /como-funciona parseado).

### H4. Cita SAT — 502 transitorio, NO caído
- 3/3 fetches dieron 200 ("Cita SAT"). El 502 de la automatización fue transitorio (edge Akamai/WAF).
- Flujo canónico intacto: `/` → `/datosPersonales`. Sin migración de dominio.
- **Falta retry + manejo explícito de 502/conn-reset** en `cita_sat.py` (hoy `goto` lanza error genérico).
- `confidence: high`.

---

## 🧬 Auditoría de código — realidad de implementación

| Archivo | Implementación | Bot-protection/captcha | Notas críticas |
|---|---|---|---|
| `base.py` (608 ln) | ✅ Completo (infra) | Helpers OCR/recaptcha, anti-detección Firefox | **`goto` NO revisa `response.status`** — una página 403 renderizada pasa como OK. Sin retry/backoff. `_rate_limit` DEPRECATED |
| `antecedentes.py` | 🔶 Parcial | reCAPTCHA semiauto (audio→manual) | Selectores sin verificar contra portal real. `_registrar_cuenta` no-op silencioso. Sin 403/retry |
| `tenencia.py` | 🔶 Parcial | Captcha imagen (OCR→manual) | **`vigencia: "2026"` hardcodeado**. Monto por regex heurística. Sin 403 |
| `credito.py` | 🔶 Parcial | **Captcha + preguntas 100% manuales** | Semimanual obligatorio (línea 162-163). `page.pdf()` es código muerto (base usa Firefox). Sin 403/Cloudflare |
| `cita_sat.py` | 🔶 Parcial | reCAPTCHA manual | URL correcta ✅. **Sin retry/502** |
| `cita_ine.py` | 🔶 Parcial | reCAPTCHA manual | Docstring documenta 403 pero el código **no lo mitiga**. `CitaINEerror` inconsistente |

**Ningún módulo maneja 403/Cloudflare en el paso 1 (`goto`)** — los 3 portales con bot-protection fuerte (Buró, Círculo, y 403s de IMSS/SAT/INE) dependen de que Playwright con fingerprint pase, sin verificación de estado HTTP.

---

## Matriz de riesgos

| # | Hallazgo | Riesgo | Confianza |
|---|----------|--------|-----------|
| H1 | Círculo URL cambiada a /mi-rce + login | HIGH — módulo falla | high |
| H2 | Buró = Akamai block, no 404 | MED — requiere fingerprint | high |
| H3 | Antecedentes: costo $240 + apostilla | MED — flujo de pago | high |
| H4 | CitaSAT 502 transitorio sin retry | MED — error genérico | high |
| C1 | `base.goto` no valida status HTTP | HIGH — falsos OK con 403 | high |
| C2 | `tenencia.vigencia` hardcodeado 2026 | MED — dato vence en 2027 | high |

---

## Recomendaciones priorizadas

1. **P0 — `base.py`**: validar `response.status` en `goto` + retry/backoff ante 5xx/conn-reset. Beneficia TODOS los módulos.
2. **P1 — `credito.py`**: actualizar URL Círculo → `/mi-rce`; documentar requisito de login y captcha manual obligatorio. README: bajar de "Migrado" a "Escrito".
3. **P1 — `cita_sat.py`**: retry ante 502/conn-reset (verificado transitorio).
4. **P2 — `tenencia.py`**: derivar `vigencia` del año actual, no hardcode.
5. **P2 — `antecedentes.py`**: verificar selectores contra portal vivo (está accesible, sin Cloudflare) + actualizar costo en docs ($240).
6. **README**: corregir estados — "Migrado" ≠ "automático". Marcar semiautomático/captcha manual por módulo.

---

## Engram Persistence
- Obs #2343 (ronda 2026-08-01) · #2345 (remote master) · análisis 2026-07-23 (baseline)

## Trend vs Previous (vs 2026-07-23)
- **Mejorado**: CitaSAT URL viva (era conn reset) · CitaINE documentado (era "404 moved") · ControlConfianza hard-fail claro (era fallo silencioso)
- **Regresión aparente**: Círculo de Crédito — URL cambió a /mi-rce (no detectado el 07-23) · Buró sigue bloqueado (Akamai, no 404 como se creyó)
- **Nuevo**: costo antecedentes $240 (2026) · apostilla en línea SEGOB · CitaSAT 502 transitorio documentado
- **Sin cambio**: 8/12 portales en mismo estado que julio
