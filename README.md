# 🤖 Agente Automatizador de Trámites GOB.MX

**Reduce trámites gubernamentales de 10-25 min a <2 min.**
Todo corre local en tu PC. Sin modelos de pago externos (aunque 2captcha es opcional para reCAPTCHA).

### Módulos activos

| Trámite | Portal | Tiempo | Estado |
|---|---|---|---|
| **CURP** (consulta + PDF) | RENAPO | ~16s | ✅ Producción |
| **NSS IMSS** | Portal IMSS | ~30-60s | ✅ Producción |
| Antecedentes No Penales | — | ~45-90s | 🔶 Escrito |
| Tenencia Vehicular | — | ~20-40s | 🔶 Escrito |

---

## ⚡ Instalación

```bash
# 1. Clonar
git clone https://github.com/LuisAlbertoMK/automatizacion.git
cd automatizacion

# 2. Dependencias
pip install -r requirements.txt

# 3. Navegador
playwright install firefox

# 4. Configurar
cp config.example.env config.env
# Editá config.env con tus datos

# 5. Probar
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
├── main.py              # Entry point CLI
├── api.py               # API REST (FastAPI)
├── exceptions.py         # Jerarquía de excepciones
├── modules/
│   ├── base.py           # BaseModule (browser lifecycle, logging, rate limiting)
│   ├── curp.py           # Módulo CURP
│   ├── nss.py            # Módulo NSS IMSS
│   ├── antecedentes.py   # Antecedentes No Penales
│   ├── tenencia.py       # Tenencia Vehicular
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

Ver `ROADMAP_COMPLETO.md` para el plan detallado con 7 fases y 3 gap analyses (rendimiento, seguridad, escalabilidad).

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
