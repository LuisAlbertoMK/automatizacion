# 🤖 Agente Automatizador de Trámites GOB.MX

**Reduce trámites gubernamentales de 10-25 min a <2 min.**
Todo corre local en tu PC. Sin modelos de pago externos (aunque 2captcha es opcional para reCAPTCHA).

### Módulos activos

| Trámite | Portal | Tiempo | Estado |
|---|---|---|---|
| **CURP** (consulta + PDF) | RENAPO | ~16s | ✅ Producción |
| **NSS IMSS** | Portal IMSS | ~30-60s | ✅ Producción |
| **RFC SAT** | SAT | ~30s | ⚙️ Migrado |
| **Acta de Nacimiento** | RENAPO | ~30-60s | ⚙️ Migrado |
| **Cita Pasaporte SRE** | SRE | ~2-5min | ⚙️ Migrado |
| **Semanas Cotizadas IMSS** | IMSS | ~30s | ⚙️ Migrado |
| Antecedentes No Penales | — | ~45-90s | 🔶 Escrito |
| Tenencia Vehicular | — | ~20-40s | 🔶 Escrito |
| Control de Confianza | SESNSP | — | ❌ Portal muerto (DNS dead 2025) |
| Buró de Crédito | buro de crédito | ~5-10min | 🔶 Semimanual (Akamai + captcha manual) |
| Círculo de Crédito | círculo de crédito | ~5-10min | 🔶 Semimanual (Cloudflare + login, /mi-rce) |
| Cita INE | INE | ~5min | ⚙️ Migrado |
| Cita SAT | SAT | ~5min | ⚙️ Migrado |

---

## 🔐 Variables de Entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `STORAGE_KEY` | ✅ | Clave Fernet para cifrar perfiles guardados |
| `IMAP_EMAIL` / `IMAP_PASSWORD` | ⚠️ | Cuenta IMAP para recibir PDFs (módulos que envían por correo) |
| `HEADLESS` | no | Browser en modo headless (`true`/`false`) |
| `REQUEST_DELAY` | no | Delay entre requests (default `2.0`) |
| `CAPTCHA_API_KEY` | no | API key de 2captcha para reCAPTCHA (opcional; sin ella el captcha es manual) |
| `ANTHROPIC_API_KEY` | no | Clave de Claude para módulos con IA (cv, escrito) |
| `API_KEY` | ✅ en PROD | Auth de la API REST (en producción el arranque aborta si falta) |
| `LOG_DIR` / `OUTPUT_DIR` | no | Directorios de logs y salida (default `logs/`, `output/`) |
| `KDF_ROUNDS` | no | Rondas bcrypt.kdf (default 600k; bajo para tests/desarrollo) |

Los secrets se guardan con prioridad: **Windows Credential Manager** → `config.env` → variables de entorno.
Ver `src/utils/secrets_manager.py` y `config.example.env` para más detalle.

---

## ⚡ Instalación

```bash
# 1. Clonar
git clone https://github.com/LuisAlbertoMK/automatizacion.git
cd automatizacion

# 2. Dependencias
pip install -r requirements.lock

# 3. Navegador
playwright install firefox

# 4. Instalar el paquete (entry point `tramites`)
pip install -e . --no-deps

# 5. Configurar
cp config.example.env config.env
# Editá config.env con tus datos

# 6. Probar
python health_check.py
```

### Con Docker

```bash
docker compose build
docker compose run --rm tramites --tramite curp --curp XXXX
```

---

## 🚀 Uso

```bash
# Modo interactivo
python main.py

# Modo directo
python main.py --tramite curp --curp XXXX
python main.py --tramite nss --curp XXXX --correo a@b.com
python main.py --perfil juan_garcia

# API REST (requiere FastAPI: pip install fastapi uvicorn)
uvicorn src.api:app --reload
# O con Docker:
docker compose --profile api up
```

---

## 🏗️ Arquitectura

```
src/
├── main.py              # Entry point CLI (tramites)
├── api.py               # API REST (FastAPI)
├── exceptions.py         # Jerarquía de excepciones
├── tramites/
│   ├── base.py           # BaseModule (browser lifecycle, logging, rate limiting)
│   ├── curp.py           # Módulo CURP
│   ├── nss.py            # Módulo NSS IMSS
│   ├── antecedentes.py   # Antecedentes No Penales
│   ├── tenencia.py       # Tenencia Vehicular
│   ├── rfc.py            # RFC SAT ⚙️ Migrado
│   ├── acta_nacimiento.py # Acta de Nacimiento RENAPO ⚙️ Migrado
│   ├── pasaporte.py      # Cita Pasaporte SRE ⚙️ Migrado
│   ├── semanas.py        # Semanas Cotizadas IMSS ⚙️ Migrado
│   ├── control_confianza.py # Control de Confianza SESNSP ❌ Portal muerto
│   ├── credito.py        # Buró + Círculo de Crédito ⚙️ Migrado
│   ├── cita_ine.py       # Cita INE ⚙️ Migrado
│   ├── cita_sat.py       # Cita SAT ⚙️ Migrado
│   ├── orchestrator.py   # Orquestador multimodal
│   └── template.py       # Template para nuevos trámites
└── utils/
    ├── captcha.py        # 2captcha client
    ├── free_captcha.py   # OCR + Whisper gratuito
    ├── ocr.py            # Tesseract OCR wrapper
    ├── storage.py        # Perfiles encriptados
    ├── logger.py         # Logging estructurado
    ├── mail_reader.py    # IMAP client
    ├── voice_input.py    # Whisper voz
    └── multimodal_input.py
```

---

## 🗺️ Roadmap

Ver `docs/ROADMAP_COMPLETO.md` para el plan detallado con 7 fases y 3 gap analyses (rendimiento, seguridad, escalabilidad).

Resumen de lo implementado:

| Fase | Estado |
|---|---|
| F0: Consolidación estructural | ✅ Completado |
| F1: Seguridad y secretos | ✅ Completado |
| F2: Rendimiento | ✅ Completado |
| F3: Tests y robustez | ✅ Health check |
| F4: Nuevos trámites | 🔶 Template listo |
| F5: DevOps | ✅ Docker + CI + API |
| F6: Captcha CNN 99% | 🔶 Pipeline dataset |

---

## 📊 Health Check

```bash
python health_check.py
```

Verifica dependencias, módulos, configuración y estado del repo.

## 🔧 Herramientas

```bash
# Generar dataset sintético para captcha CNN
python tools/generate_dataset.py --augment
python tools/generate_dataset.py --auto-label
```

---

## 🔒 Seguridad

- Perfiles encriptados con **Fernet** (cryptography)
- Passwords hasheados con **pbkdf2_hmac** + salt
- Rate limiting configurable (`REQUEST_DELAY`)
- Modo headless por defecto
- `config.env` excluido de git
