# CAPTCHA NSS — Enfoque PAGO

## Target
Portal IMSS/NSS: hCaptcha / reCAPTCHA v2/v3 — producción, alta tasa de éxito.

---

## Servicios recomendados

| Servicio | Tipo | Precio aprox. | Tasa éxito |
|---|---|---|---|
| **CapSolver** | IA + humano | $0.80–1.50 / 1k | 95%+ |
| **2Captcha** | Humano | $0.50–1.00 / 1k | 98%+ |
| **Anti-Captcha** | Humano + IA | $0.70–1.20 / 1k | 97%+ |
| **NoCaptchaAI** | IA | $1.00–2.00 / 1k | 93%+ |
| **Bright Data** | Proxy + solver | desde $15/mes | 99%+ |

> **Recomendado para NSS**: **CapSolver** (mejor balance precio/velocidad para hCaptcha)

---

## Flujo técnico (Playwright + CapSolver)

```
1. Playwright Chromium headless stealth
2. Navegar a portal NSS
3. Detectar sitekey hCaptcha del DOM
4. POST a CapSolver API → task type: HCaptchaTask
5. Poll resultado (avg 3–8s)
6. Inyectar token en input h-captcha-response
7. Trigger submit
8. Verificar respuesta → retry si falla
```

---

## Código base (Node.js)

```js
import { chromium } from 'rebrowser-playwright';

const CAPSOLVER_KEY = process.env.CAPSOLVER_KEY;
const NSS_URL = 'https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/...';

async function solveHCaptcha(sitekey, pageUrl) {
  // Create task
  const create = await fetch('https://api.capsolver.com/createTask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      clientKey: CAPSOLVER_KEY,
      task: {
        type: 'HCaptchaTask',   // con proxyless: HCaptchaTaskProxyless
        websiteURL: pageUrl,
        websiteKey: sitekey,
      }
    })
  }).then(r => r.json());

  const taskId = create.taskId;

  // Poll
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const res = await fetch('https://api.capsolver.com/getTaskResult', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clientKey: CAPSOLVER_KEY, taskId })
    }).then(r => r.json());

    if (res.status === 'ready') return res.solution.gRecaptchaResponse;
  }
  throw new Error('CAPTCHA timeout');
}

async function consultaNSS(nss) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(NSS_URL);

  // Extraer sitekey
  const sitekey = await page.$eval('[data-sitekey]', el => el.dataset.sitekey);

  const token = await solveHCaptcha(sitekey, NSS_URL);

  // Inyectar token
  await page.evaluate(t => {
    document.querySelector('[name="h-captcha-response"]').value = t;
    document.querySelector('[name="g-recaptcha-response"]').value = t;
  }, token);

  await page.fill('#nss', nss);
  await page.click('#btnConsultar');
  await page.waitForSelector('#resultado', { timeout: 10000 });

  const resultado = await page.$eval('#resultado', el => el.innerText);
  await browser.close();
  return resultado;
}
```

---

## Anti-detección esencial (pago = producción)

| Capa | Solución | Costo |
|---|---|---|
| Fingerprint browser | `rebrowser-playwright` | Gratis |
| Mouse humano | `ghost-cursor` | Gratis |
| IP residencial | Bright Data / Oxylabs | $15+/mes |
| TLS fingerprint | `cycletls` o `tls-client` | Gratis |
| Headers HTTP | Rotación UA + Accept-Language MX | Gratis |

---

## Arquitectura para automatización en escala

```
┌─────────────────┐
│  Queue (Bull)   │  ← NSS array input
└────────┬────────┘
         │
┌────────▼────────┐
│ Worker Pool (N) │  ← N instancias Playwright paralelas
└────────┬────────┘
         │
┌────────▼────────┐
│  CapSolver API  │  ← CAPTCHA resuelto
└────────┬────────┘
         │
┌────────▼────────┐
│   DB / Export   │  ← MySQL / CSV resultado
└─────────────────┘
```

---

## Gaps a cubrir (producción)

- [ ] **Proxy pool** rotativo con IPs MX residenciales
- [ ] **Session persistence** — cookies/localStorage para evitar CAPTCHA en recargas
- [ ] **Rate limiting propio** — no sobrepasar límite IMSS (riesgo ban IP)
- [ ] **Error handling** — CAPTCHA inválido / sesión expirada / mantenimiento portal
- [ ] **Logging** — registrar tasa éxito por sesión, detectar cambios en portal
- [ ] **Token refresh** — hCaptcha token caduca en ~2 min; resolver justo antes de submit

---

## Costos estimados (100 consultas/día)

| Item | Costo/mes |
|---|---|
| CapSolver (~3k CAPTCHA) | ~$3 |
| Proxies residenciales MX | $15–30 |
| VPS Node.js | $5–10 |
| **Total** | **~$23–43/mes** |

