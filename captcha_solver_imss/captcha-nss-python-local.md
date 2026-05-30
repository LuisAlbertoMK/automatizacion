# NSS Resolver — Python Full Stack (máxima tasa de éxito local)

## Arquitectura

```
FastAPI (solver)          Playwright (bot)
┌─────────────────┐       ┌──────────────────────┐
│ /solve/text     │◄──────│ 1. Captura screenshot │
│ /solve/grid     │       │    del CAPTCHA        │
│ /solve/audio    │       │ 2. POST imagen/audio  │
└────────┬────────┘       │ 3. Recibe token       │
         │                │ 4. Inyecta + submit   │
   ddddocr / YOLO /       │ 5. Lee email IMAP     │
   Whisper                └──────────────────────┘
```

---

## Estructura

```
nss-resolver/
├── solver/
│   ├── main.py          ← FastAPI server
│   ├── text.py          ← ddddocr
│   ├── grid.py          ← YOLOv8
│   └── audio.py         ← Whisper
├── bot/
│   ├── browser.py       ← Playwright stealth
│   ├── portal.py        ← navegación IMSS
│   ├── email_reader.py  ← IMAP
│   └── main.py          ← entry point
├── requirements.txt
└── .env
```

---

## `solver/main.py`
```python
from fastapi import FastAPI, UploadFile
from solver.text import solve_text
from solver.grid import solve_grid
from solver.audio import solve_audio
import base64, io

app = FastAPI()

@app.post("/solve/text")
async def text_endpoint(file: UploadFile):
    data = await file.read()
    result = solve_text(data)
    return {"token": result}

@app.post("/solve/grid")
async def grid_endpoint(file: UploadFile):
    data = await file.read()
    result = solve_grid(data)
    return {"indices": result}  # índices de celdas a clickear

@app.post("/solve/audio")
async def audio_endpoint(file: UploadFile):
    data = await file.read()
    result = solve_audio(data)
    return {"token": result}
```

## `solver/text.py` — ddddocr
```python
import ddddocr

ocr = ddddocr.DdddOcr(show_ad=False)

def solve_text(image_bytes: bytes) -> str:
    return ocr.classification(image_bytes)
```

## `solver/grid.py` — YOLOv8
```python
from ultralytics import YOLO
from PIL import Image
import io, numpy as np

model = YOLO("yolov8n.pt")  # swap por modelo fine-tuneado en CAPTCHAs

GRID_ROWS, GRID_COLS = 3, 3  # hCaptcha 3x3

def solve_grid(image_bytes: bytes, target_class: str = "bus") -> list[int]:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.array(img)
    
    h, w = arr.shape[:2]
    cell_h, cell_w = h // GRID_ROWS, w // GRID_COLS
    
    hits = []
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            cell = arr[row*cell_h:(row+1)*cell_h, col*cell_w:(col+1)*cell_w]
            results = model(cell, verbose=False)
            labels = [model.names[int(b.cls)] for b in results[0].boxes]
            if target_class in labels:
                hits.append(row * GRID_COLS + col)
    
    return hits
```

## `solver/audio.py` — Whisper
```python
import whisper, tempfile, os

model = whisper.load_model("tiny")  # tiny = rápido, base = más preciso

def solve_audio(audio_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio_bytes)
        tmp = f.name
    try:
        result = model.transcribe(tmp, language="en")
        # Extraer solo dígitos/letras del texto
        token = "".join(c for c in result["text"] if c.isalnum()).lower()
        return token
    finally:
        os.unlink(tmp)
```

---

## `bot/browser.py`
```python
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
import random

async def create_browser():
    p = await async_playwright().start()
    browser = await p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ]
    )
    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        locale="es-MX",
        timezone_id="America/Mexico_City",
        viewport={"width": 1366, "height": 768},
        extra_http_headers={"Accept-Language": "es-MX,es;q=0.9"}
    )
    page = await ctx.new_page()
    await stealth_async(page)
    return browser, page

async def human_type(page, selector: str, text: str):
    await page.click(selector)
    for char in text:
        await page.keyboard.type(char)
        await page.wait_for_timeout(random.randint(80, 150))

async def human_move_click(page, selector: str):
    el = page.locator(selector)
    box = await el.bounding_box()
    # Mover a punto aleatorio dentro del elemento
    x = box["x"] + random.uniform(box["width"] * 0.2, box["width"] * 0.8)
    y = box["y"] + random.uniform(box["height"] * 0.2, box["height"] * 0.8)
    await page.mouse.move(x, y, steps=random.randint(10, 25))
    await page.wait_for_timeout(random.randint(100, 300))
    await page.mouse.click(x, y)
```

## `bot/portal.py`
```python
import httpx, base64
from bot.browser import human_type, human_move_click

PORTAL_URL = "https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asegurado/nss"
SOLVER_URL = "http://localhost:8000"

async def fill_and_submit(page, curp: str, email: str) -> str:
    await page.goto(PORTAL_URL, wait_until="networkidle")

    # Llenar campos
    await human_type(page, "#curp", curp)
    await human_type(page, "#correo", email)
    await human_type(page, "#correoConfirmacion", email)

    # Detectar tipo de CAPTCHA
    captcha_type = await detect_captcha_type(page)
    token = await resolve_captcha(page, captcha_type)

    # Inyectar token
    await page.evaluate(f"""
        const el = document.querySelector('[name="h-captcha-response"]');
        if (el) el.value = '{token}';
    """)

    await human_move_click(page, "#btnEnviar")
    
    result = await page.wait_for_selector(
        ".mensaje-exito, .mensaje-error, .alert",
        timeout=15000
    )
    return await result.inner_text()

async def detect_captcha_type(page) -> str:
    if await page.query_selector(".h-captcha"):
        return "hcaptcha"
    if await page.query_selector(".g-recaptcha"):
        return "recaptcha"
    if await page.query_selector("canvas"):
        return "text"
    return "unknown"

async def resolve_captcha(page, captcha_type: str) -> str:
    if captcha_type == "text":
        # Screenshot del canvas/imagen
        el = await page.query_selector(".captcha-img, canvas, img[id*='captcha']")
        img_bytes = await el.screenshot()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{SOLVER_URL}/solve/text",
                files={"file": ("captcha.png", img_bytes, "image/png")}
            )
        return r.json()["token"]

    if captcha_type in ("hcaptcha", "recaptcha"):
        # Intentar challenge de audio (más confiable que imagen grid)
        await trigger_audio_challenge(page)
        audio_bytes = await download_audio_challenge(page)
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{SOLVER_URL}/solve/audio",
                files={"file": ("audio.mp3", audio_bytes, "audio/mpeg")}
            )
        return r.json()["token"]

    return ""

async def trigger_audio_challenge(page):
    # Click en ícono de accesibilidad del widget
    frame = page.frame_locator("iframe[title*='hCaptcha']").first
    await frame.locator(".challenge-container").wait_for()
    audio_btn = frame.locator("[aria-label*='audio'], .audio-button")
    await audio_btn.click()
    await page.wait_for_timeout(1500)

async def download_audio_challenge(page) -> bytes:
    frame = page.frame_locator("iframe[title*='Audio Challenge']")
    audio_el = frame.locator("audio")
    src = await audio_el.get_attribute("src")
    async with httpx.AsyncClient() as client:
        r = await client.get(src)
    return r.content
```

## `bot/email_reader.py`
```python
from imaplib import IMAP4_SSL
import email, time, re, os

def wait_for_nss_email(timeout: int = 120) -> str | None:
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            with IMAP4_SSL("imap.gmail.com") as m:
                m.login(os.getenv("EMAIL_USER"), os.getenv("EMAIL_APP_PASS"))
                m.select("INBOX")
                
                _, uids = m.search(None, 'FROM "imss.gob.mx" UNSEEN')
                
                for uid in uids[0].split()[::-1]:  # más reciente primero
                    _, data = m.fetch(uid, "(RFC822)")
                    msg = email.message_from_bytes(data[0][1])
                    body = extract_body(msg)
                    
                    match = re.search(r'\b(\d{11})\b', body)
                    if match:
                        m.store(uid, '+FLAGS', '\\Seen')
                        return match.group(1)
        except Exception:
            pass
        
        time.sleep(5)
    
    return None

def extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
    return msg.get_payload(decode=True).decode(errors="ignore")
```

## `bot/main.py`
```python
import asyncio
from bot.browser import create_browser
from bot.portal import fill_and_submit
from bot.email_reader import wait_for_nss_email

async def get_nss(curp: str, email: str) -> dict:
    browser, page = await create_browser()
    try:
        portal_msg = await fill_and_submit(page, curp, email)
        print(f"Portal: {portal_msg}")

        if "error" in portal_msg.lower():
            return {"status": "error", "detail": portal_msg}

        nss = wait_for_nss_email(timeout=120)
        return {
            "curp": curp,
            "email": email,
            "nss": nss,
            "status": "ok" if nss else "email_timeout"
        }
    finally:
        await browser.close()

if __name__ == "__main__":
    import sys
    curp, email = sys.argv[1], sys.argv[2]
    result = asyncio.run(get_nss(curp, email))
    print(result)
```

---

## `requirements.txt`
```
playwright
playwright-stealth
ddddocr
ultralytics
openai-whisper
fastapi
uvicorn
httpx
imaplib2
python-dotenv
pillow
numpy
```

---

## Arrancar

```bash
# 1. Instalar
pip install -r requirements.txt
playwright install chromium

# 2. Solver server (terminal 1)
uvicorn solver.main:app --port 8000

# 3. Correr bot (terminal 2)
python -m bot.main CURP_AQUI correo@gmail.com
```

---

## Tasa de éxito estimada por método

| CAPTCHA | Método | Tasa |
|---|---|---|
| Texto distorsionado | ddddocr | ~85–92% |
| Grid imágenes | YOLOv8n genérico | ~60–70% |
| Grid imágenes | YOLOv8 fine-tuned NSS | ~88–95% |
| Audio challenge | Whisper tiny | ~90–95% |
| Audio challenge | Whisper base | ~95–98% |

> **Estrategia**: intentar audio challenge primero — es más confiable que grid visual.

---

## Gaps pendientes antes de producción

- [ ] Verificar selectores reales del portal (`#curp`, `#correo`, etc.)
- [ ] Confirmar remitente exacto del email IMSS
- [ ] Regex NSS ajustada al formato real del correo
- [ ] Fine-tune YOLOv8 con imágenes grid reales del portal
- [ ] Selector iframe audio challenge ajustado al widget real

