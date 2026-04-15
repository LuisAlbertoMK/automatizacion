# 🤖 Agente Automatizador de Trámites GOB.MX
### Módulos: CURP + NSS IMSS — v1.0 (marzo 2026)

Automatiza consultas de CURP y NSS en menos de 60 segundos.
Sin modelos de pago externos. Todo corre local en tu PC.

---

## 📋 Requisitos

- Python 3.10 o superior
- 4 GB RAM mínimo
- Conexión a internet (solo para el trámite)
- Cuenta en 2captcha.com con crédito (~$2 USD)

---

## ⚡ Instalación rápida

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Instalar navegadores de Playwright
playwright install chromium

# 3. Copiar y editar configuración
cp config.example.env config.env
# Edita config.env con tu API key de 2captcha

# 4. Ejecutar
python main.py
```

---

## 🗂 Estructura del proyecto

```
tramites_agent/
├── main.py                  # Punto de entrada — CLI interactivo
├── config.env               # Tu API key y configuración (NO subir a git)
├── config.example.env       # Plantilla de configuración
├── requirements.txt
├── modules/
│   ├── curp.py              # Módulo CURP (gob.mx/curp)
│   └── nss.py               # Módulo NSS IMSS
├── utils/
│   ├── captcha.py           # Cliente 2captcha
│   ├── mail_reader.py       # Lector IMAP para correo IMSS
│   ├── storage.py           # Perfil local del cliente (encriptado)
│   └── pdf_handler.py       # Descarga y verificación de PDFs
├── data/
│   └── perfiles.json        # Perfiles guardados (encriptado)
└── output/                  # PDFs descargados
```

---

## 🚀 Uso

```bash
# Modo interactivo
python main.py

# Modo directo (un solo trámite)
python main.py --tramite curp --curp XXXX800101HDFXXX00

# Con perfil guardado
python main.py --tramite nss --perfil juan_garcia
```

---

## 💰 Costo real por trámite

| Trámite          | Costo oficial | Costo CAPTCHA aprox |
|------------------|---------------|----------------------|
| CURP             | $0 MXN        | ~$0.002 USD          |
| NSS IMSS         | $0 MXN        | ~$0.004 USD          |
| **Total aprox.** | **$0 MXN**    | **< $0.01 USD**      |

---

## ⚠️ Aviso legal

Este software automatiza el llenado de formularios públicos con datos
propios del usuario. No almacena ni transmite datos a terceros.
El uso es responsabilidad del usuario final.
