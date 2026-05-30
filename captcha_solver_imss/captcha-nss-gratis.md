# CAPTCHA NSS — Enfoque GRATIS

## Target
Portal IMSS/NSS: hCaptcha / reCAPTCHA v2 visual + posibles desafíos de imagen.

---

## Stack base
- **Playwright** + Chromium (stealth)
- **python** o **Node.js**
- Solver: modelo local o API gratuita con límites

---

## Herramientas recomendadas

| Tool | Rol | Límite gratis |
|---|---|---|
| `playwright-stealth` / `rebrowser-playwright` | Evasión fingerprint | ∞ |
| `2captcha` trial | Resolución humana | ~100 gratis |
| `capsolver` free tier | IA solver | 1k/mes |
| `YOLOv8` local | Clasificación imágenes CAPTCHA | ∞ CPU |
| `ddddocr` | OCR texto distorsionado | ∞ |

---

## Flujo técnico

```
1. Lanzar Chromium headless (stealth)
2. Detectar tipo CAPTCHA en DOM
3. Si texto/distorsión → ddddocr
4. Si imagen grid (bus, semáforo…) → YOLOv8 local
5. Si audio challenge → speech-to-text local (whisper.cpp)
6. Inyectar solución vía JS / click simulado
7. Retry con backoff exponencial (max 3)
```

---

## Setup básico (Node + Playwright)

```js
import { chromium } from 'rebrowser-playwright';
import Ddddocr from 'ddddocr'; // wrapper Node o llamar Python subprocess

const browser = await chromium.launch({
  headless: true,
  args: ['--disable-blink-features=AutomationControlled']
});

const ctx = await browser.newContext({
  userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)...',
  viewport: { width: 1280, height: 720 }
});

const page = await ctx.newPage();
await page.goto('https://serviciosdigitales.imss.gob.mx/...');

// Detectar iframe hCaptcha
const frame = page.frameLocator('iframe[src*="hcaptcha"]');
// Extraer imagen del challenge y pasar a solver
```

---

## Imágenes / modelos recomendados

| Dataset/Modelo | Uso |
|---|---|
| `ultralytics/YOLOv8n` | Grid images (bus, bicicleta, etc.) |
| `ddddocr` | CAPTCHA texto distorsionado |
| `openai/whisper-tiny` | Audio CAPTCHA |
| Dataset: `captcha-collection` (HuggingFace) | Fine-tune propio |

---

## Gaps a cubrir

- [ ] **Fingerprint TLS** — usar `tls-client` o cycletls
- [ ] **Canvas fingerprint** — spoofear con stealth plugin
- [ ] **Mouse entropy** — movimientos humanos con `ghost-cursor`
- [ ] **IP rotation** — proxies residenciales libres (limitados) o TOR
- [ ] **Timing** — delays variables, no robóticos
- [ ] **Token expiry** — hCaptcha token dura ~2 min, resolver justo antes de submit

---

## Caveats

- Solvers gratuitos tienen latencia alta (5–30s) o límites diarios bajos.
- YOLOv8 local requiere fine-tune en CAPTCHAs de IMSS específicamente.
- NSS puede bloquear por fingerprint aunque resuelvas el CAPTCHA.
