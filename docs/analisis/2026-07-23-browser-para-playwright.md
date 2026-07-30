# Análisis: Mejor Browser para Playwright — Chrome vs Firefox vs Chromium

**Fecha:** 2026-07-23  
**Objetivo:** Determinar qué browser usar para automatización de trámites gubernamentales mexicanos.

---

## Estado actual del proyecto

- **Browser:** Firefox (`p.firefox.launch()`)
- **Playwright:** v1.61.0
- **Stealth:** Solo `navigator.webdriver = undefined` (init script básico)
- **Browser Pool:** Sí — pool de 2 instancias Firefox pre-lanzadas
- **User-Agent:** Firefox 131.0 real (no Chrome UA sobre Firefox)
- **No tiene:** `playwright-stealth`, Camoufox, Patchright, ni nodriver

---

## Benchmarks 2026 — Resultados reales

### Benchmark 1: Anti-Detect Browser Benchmark (651 verdicts, 31 targets)

| Browser | OK | Gated | Blocked | Engine |
|---------|-----|-------|---------|--------|
| **nodriver** | 28 | 3 | **0** | Chrome 148 (system) |
| CloakBrowser | 26 | 3 | 2 | Chromium 145 |
| curl_cffi | 26 | 3 | 2 | HTTP impersonate=chrome |
| **Patchright** | 25 | 3 | 3 | Chrome 148 (channel=chrome) |
| **Camoufox** | 25 | 3 | 3 | Firefox 135 (patched C++) |
| Vanilla Playwright | 24 | 2 | **5** | Chromium 147 |
| rebrowser-playwright | 24 | 2 | 5 | Chromium 136 |

### Benchmark 2: Browser Automation Benchmark (10 protection systems)

| Engine | Bypass Rate | Mem (MB) |
|--------|-------------|----------|
| **Patchright (headed)** | **100%** | 1,314 |
| CloakBrowser | 90% | — |
| **Camoufox (headless)** | **90%** | — |
| nodriver-chrome | 80% | — |
| Playwright Chrome (headed) | 60% | — |
| Playwright Firefox | 60% | — |
| **Playwright Chrome (headless)** | **40%** | 517 |
| Playwright Firefox (headless) | 60% | — |

### Benchmark 3: reCAPTCHA v3 scores

| Engine | Score |
|--------|-------|
| Patchright | 0.90 |
| Camoufox | 0.90 |
| Vanilla Playwright | **0.90** |
| nodriver | 0.90 |

**Nota:** Todos pasan reCAPTCHA v3. El problema son Cloudflare, DataDome, Akamai.

---

## Análisis por categoría

### 🏆 nodriver — El mejor absoluto
- **0 bloqueados** en 31 targets
- Usa Chrome del sistema vía CDP directo (sin Playwright shim)
- **Contra:** Requiere Python, solo Chrome, sin API de Playwright
- **Ideal para:** Scraping pesado con Cloudflare

### 🥈 Patchright — El mejor Playwright-based
- Playwright fork que parcha `Runtime.enable` y `Target.setAutoAttach`
- Usa `channel=chrome` → Chrome 148 real
- **100% bypass rate** headed
- **Contra:** 2x memoria que vanilla Playwright
- **Ideal para:** Drop-in replacement de Playwright existente

### 🥉 Camoufox — El mejor Firefox
- Firefox 135 parchado a nivel C++ (no JS)
- **90% bypass rate** headless
- API compatible con Playwright
- **Contra:** Solo Firefox, ~300MB download inicial
- **Ideal para:** Sitios que whitelistean Firefox o detectan Chrome

### Vanilla Playwright (lo que tenemos)
- **60% headed, 40% headless** en Chromium
- **60% headed, 60% headless** en Firefox
- Detectable por: `navigator.webdriver`, CDP handshake, TLS fingerprint

---

## Para portales gubernamentales mexicanos específicamente

### ¿Qué anti-bot usan?

| Portal | Protección | Nivel |
|--------|-----------|-------|
| gob.mx | Cloudflare | 🔴 Alto |
| sat.gob.mx | Custom + posible Cloudflare | 🟡 Medio |
| imss.gob.mx | Custom (CAPTCHA imagen) | 🟢 Bajo |
| consultas.curp.gob.mx | Custom (CAPTCHA numérico) | 🟢 Bajo |
| citas.sre.gob.mx | Custom | 🟡 Medio |
| citas.ine.mx | Custom | 🟡 Medio |

### Firefox ya es buena elección para este caso

1. **Menos escrutinio que Chromium** — la mayoría de bots usan Chromium, los portales gubernamentales pesan más chromium-shaped traffic
2. **Firefox tiene TLS fingerprint diferente** — los detectores de Cloudflare buscan JA3/JA4 de Chromium
3. **Ya lo tenés configurado** con UA real de Firefox (no Chrome UA sobre Firefox)
4. **Los CAPTCHAs de gobierno son simples** — imagen numérica, no reCAPTCHA v3 avanzado

---

## Recomendación

### Corto plazo (HOY): Mantener Firefox + agregar playwright-stealth

**Por qué:**
- Firefox ya es buena elección para portales gubernamentales
- `playwright-stealth` parcha: `navigator.webdriver`, plugins, mimeTypes, chrome.runtime, permissions
- Costo: 1 pip install + 5 líneas de código
- Gana ~10-15% en bypass rate

**Implementación:**
```bash
pip install playwright-stealth
```

```python
from playwright_stealth import stealth_async

# En launch_browser():
context = await browser.new_context(...)
page = await context.new_page()
await stealth_async(page)  # ← Agregar esta línea
```

### Medio plazo (si Firefox falla): Evaluar Camoufox

**Por qué:**
- 90% bypass rate headless (vs 60% vanilla Firefox)
- Parches a nivel C++ — no detectables por JS
- API compatible con Playwright (casi zero refactor)
- Ya tenés todo el código en Firefox — cambio mínimo

**Cuándo cambiar:**
- Si gob.mx o sat.gob.mx bloquean a Firefox vanilla
- Si necesitás pasar Cloudflare Turnstile sin intervention

### Largo plazo (si escalás): Patchright o nodriver

**Por qué:**
- 100% bypass rate
- Pero: más complejo, más memoria, otro paradigm

**Cuándo cambiar:**
- Si estás haciendo 1000+ trámites/día
- Si los portales implementan anti-bot agresivo

---

## Resumen de decisión

```
┌─────────────────────────────────────────────────────────┐
│  ESTADO ACTUAL                                          │
│  Firefox vanilla + webdriver=false                       │
│  Bypass rate: ~60%                                      │
│                                                         │
│  RECOMENDACIÓN INMEDIATA                                 │
│  Firefox + playwright-stealth                           │
│  Bypass rate estimado: ~70-75%                           │
│  Costo: 1 pip install + 5 líneas                        │
│                                                         │
│  ESCALADO FUTURO                                         │
│  Camoufox (Firefox patched C++)                         │
│  Bypass rate: ~90%                                      │
│  Costo: pip install camoufox + cambio mínimo            │
│                                                         │
│  MÁXIMO ESCALADO                                         │
│  Patchright (Chrome patched Playwright)                 │
│  Bypass rate: ~100%                                     │
│  Costo: refactor significativo                          │
└─────────────────────────────────────────────────────────┘
```

---

## Fuentes

- [Anti-Detect Browser Benchmark 2026](https://ianlpaterson.com/blog/anti-detect-browser-benchmark-patchright-nodriver-curl-cffi/) — 651 verdicts, 31 targets
- [Browser Automation Benchmark 2026](https://automation.techinz.dev/blog/browser-automation-benchmark-2026) — 10 protection systems
- [Playwright Bot Detection 2026](https://usefoil.com/learn/playwright-bot-detection) — Foil
- [Headless Browser Detection 2026](https://dev.to/helperx/headless-browser-detection-in-2026-what-still-trips-up-playwright-5427)
- [Playwright vs Camoufox](https://bytetunnels.com/posts/playwright-vs-camoufox-stealth-automation-head-to-head/)
- [Playwright Anti-Bot What Works 2026](https://alterlab.io/blog/playwright-bot-detection-what-actually-works-in-2026)
