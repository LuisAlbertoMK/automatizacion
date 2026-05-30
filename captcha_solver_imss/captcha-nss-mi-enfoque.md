# Mi enfoque: Automatización NSS completo
## Input: CURP + correo → Output: email de confirmación IMSS

---

## Flujo completo

```
CURP + email
     │
     ▼
1. Abrir portal IMSS con Playwright stealth
2. Llenar CURP
3. Llenar email (x2: email + confirmación)
4. Detectar sitekey hCaptcha en DOM
5. Resolver CAPTCHA vía CapSolver (~5s)
6. Inyectar token + submit
7. Capturar respuesta portal
8. Leer email de confirmación (IMAP)
9. Extraer NSS del correo
10. Retornar resultado
```

---

## Por qué este stack exacto

| Decisión | Razón |
|---|---|
| `rebrowser-playwright` no `puppeteer` | Mejor evasión CDP leak |
| `CapSolver` no `2captcha` | hCaptcha específico, más rápido |
| `gmail` + `imapflow` | IMAP confiable, fácil parse |
| **No** proxies (v1) | Portal IMSS no es agresivo en IP ban si vas lento |
| `ghost-cursor` | Mouse humano, reduce score bot |

---

## Estructura del proyecto

```
nss-resolver/
├── src/
│   ├── browser.js       ← setup stealth Playwright
│   ├── captcha.js       ← CapSolver wrapper
│   ├── portal.js        ← navegación IMSS
│   ├── email.js         ← IMAP listener
│   └── index.js         ← entry point
├── .env
└── package.json
```

---

## Código

### `browser.js`
```js
import { chromium } from 'rebrowser-playwright';
import { createCursor } from 'ghost-cursor-playwright';

export async function createBrowser() {
  const browser = await chromium.launch({
    headless: true,
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-sandbox',
      '--disable-setuid-sandbox',
    ]
  });

  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
    locale: 'es-MX',
    timezoneId: 'America/Mexico_City',
    viewport: { width: 1366, height: 768 },
    extraHTTPHeaders: {
      'Accept-Language': 'es-MX,es;q=0.9',
    }
  });

  const page = await ctx.newPage();
  const cursor = await createCursor(page);

  return { browser, page, cursor };
}
```

### `captcha.js`
```js
const API = 'https://api.capsolver.com';

export async function solveHCaptcha(sitekey, pageUrl) {
  const { taskId } = await fetch(`${API}/createTask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      clientKey: process.env.CAPSOLVER_KEY,
      task: {
        type: 'HCaptchaTaskProxyless',
        websiteURL: pageUrl,
        websiteKey: sitekey,
      }
    })
  }).then(r => r.json());

  for (let i = 0; i < 24; i++) {
    await sleep(3000);
    const res = await fetch(`${API}/getTaskResult`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clientKey: process.env.CAPSOLVER_KEY,
        taskId
      })
    }).then(r => r.json());

    if (res.status === 'ready') return res.solution.gRecaptchaResponse;
    if (res.status === 'failed') throw new Error(`CapSolver failed: ${res.errorDescription}`);
  }

  throw new Error('CAPTCHA timeout (72s)');
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
```

### `portal.js`
```js
import { solveHCaptcha } from './captcha.js';

const URL_PORTAL = 'https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asegurado/nss';

export async function consultarNSS(page, cursor, curp, email) {
  await page.goto(URL_PORTAL, { waitUntil: 'networkidle' });

  // CURP
  await cursor.move('#curp');
  await page.type('#curp', curp, { delay: randomDelay(80, 140) });

  // Email x2
  await cursor.move('#correo');
  await page.type('#correo', email, { delay: randomDelay(80, 140) });

  await cursor.move('#correoConfirmacion');
  await page.type('#correoConfirmacion', email, { delay: randomDelay(80, 140) });

  // Extraer sitekey
  const sitekey = await page.$eval(
    '[data-sitekey], .h-captcha',
    el => el.dataset.sitekey
  );

  // Resolver CAPTCHA
  const token = await solveHCaptcha(sitekey, URL_PORTAL);

  // Inyectar token
  await page.evaluate(t => {
    document.querySelector('[name="h-captcha-response"]').value = t;
    const g = document.querySelector('[name="g-recaptcha-response"]');
    if (g) g.value = t;
  }, token);

  // Submit con cursor humano
  await cursor.click('#btnEnviar');

  // Esperar confirmación portal
  const msg = await page.waitForSelector('.mensaje-exito, .mensaje-error', {
    timeout: 15000
  }).then(el => el.innerText()).catch(() => 'Sin respuesta');

  return msg;
}

const randomDelay = (min, max) => Math.floor(Math.random() * (max - min) + min);
```

### `email.js`
```js
import { ImapFlow } from 'imapflow';

export async function waitForNSSEmail(emailAddr, timeoutMs = 120000) {
  const client = new ImapFlow({
    host: 'imap.gmail.com',
    port: 993,
    secure: true,
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_APP_PASS  // Gmail App Password
    },
    logger: false
  });

  await client.connect();
  const lock = await client.getMailboxLock('INBOX');
  const start = Date.now();

  try {
    while (Date.now() - start < timeoutMs) {
      // Buscar email de IMSS reciente
      const msgs = await client.search({
        from: 'noreply@imss.gob.mx',
        since: new Date(Date.now() - 300000)  // últimos 5 min
      });

      if (msgs.length > 0) {
        const uid = msgs[msgs.length - 1];
        const msg = await client.fetchOne(uid, { source: true });
        const raw = msg.source.toString();

        // Extraer NSS del body (ajustar regex al formato real del correo)
        const nssMatch = raw.match(/NSS[:\s]+(\d{11})/i);
        if (nssMatch) return nssMatch[1];

        return raw; // retornar raw si no matchea
      }

      await sleep(5000);
    }
    throw new Error('Email timeout');
  } finally {
    lock.release();
    await client.logout();
  }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
```

### `index.js`
```js
import { createBrowser } from './src/browser.js';
import { consultarNSS } from './src/portal.js';
import { waitForNSSEmail } from './src/email.js';

export async function getNSS(curp, email) {
  const { browser, page, cursor } = await createBrowser();

  try {
    const portalMsg = await consultarNSS(page, cursor, curp, email);
    console.log('Portal:', portalMsg);

    if (portalMsg.toLowerCase().includes('error')) {
      throw new Error(`Portal rechazó: ${portalMsg}`);
    }

    const nss = await waitForNSSEmail(email);
    return { curp, email, nss, status: 'ok' };

  } catch (err) {
    return { curp, email, nss: null, status: 'error', error: err.message };
  } finally {
    await browser.close();
  }
}

// CLI rápido
const [,, curp, email] = process.argv;
if (curp && email) {
  getNSS(curp, email).then(console.log);
}
```

---

## `.env`
```env
CAPSOLVER_KEY=tu_key_aqui
EMAIL_USER=tu_cuenta@gmail.com
EMAIL_APP_PASS=xxxx_xxxx_xxxx_xxxx
```

---

## `package.json` (deps)
```json
{
  "type": "module",
  "dependencies": {
    "rebrowser-playwright": "latest",
    "ghost-cursor-playwright": "latest",
    "imapflow": "latest"
  }
}
```

---

## Lo que validaría antes de producción

| Punto | Acción |
|---|---|
| Selector `#curp`, `#correo`, `#correoConfirmacion` | Inspeccionar DOM real y ajustar |
| Sitekey selector | Confirmar atributo exacto en portal |
| Email `from` de IMSS | Verificar remitente real con un envío manual |
| Regex NSS en email | Ajustar a formato real del correo |
| `btnEnviar` selector | Confirmar ID/class real del botón |

---

## Gaps conocidos

- Si IMSS cambia DOM → ajustar selectores (1 archivo: `portal.js`)
- Si usan reCAPTCHA v3 (score-based) → cambiar task type en `captcha.js` a `ReCaptchaV3TaskProxyless`
- Para volumen alto → agregar queue con `bullmq` + workers paralelos con delay entre requests

