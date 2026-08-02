# 🚀 Guía de Instalación Completa - Sistema de Trámites GOB.MX
## Con Entrada Multimodal (Texto, Voz, Imagen)

**Fecha:** 17 de Marzo, 2026  
**Versión:** 2.0 - Multimodal  

---

## 📋 Requisitos del Sistema

### Hardware Mínimo
- **CPU:** 4 cores (Intel i5 o equivalente)
- **RAM:** 8 GB
- **Disco:** 10 GB libres
- **Micrófono:** Para entrada por voz (opcional)
- **Cámara web:** Para entrada por imagen (opcional)

### Sistema Operativo
- ✅ Windows 10/11
- ✅ macOS 10.15+
- ✅ Linux (Ubuntu 20.04+)

---

## 🔧 Instalación Paso a Paso

### Paso 1: Instalar Python 3.10+

**Windows:**
1. Descargar de: https://www.python.org/downloads/
2. Ejecutar instalador
3. ✅ Marcar "Add Python to PATH"
4. Verificar:
```powershell
python --version
# Debe mostrar: Python 3.10.x o superior
```

**macOS:**
```bash
brew install python@3.10
```

**Linux:**
```bash
sudo apt update
sudo apt install python3.10 python3-pip
```

---

### Paso 2: Clonar o Descargar el Proyecto

```powershell
cd d:\proyectos
# El proyecto ya está en: d:\proyectos\automatizacion
```

---

### Paso 3: Instalar Dependencias de Python

```powershell
cd d:\proyectos\automatizacion

# Instalar todas las dependencias
pip install -r requirements.txt
```

**Dependencias que se instalarán:**
- `playwright` - Automatización de navegador
- `openai-whisper` - Reconocimiento de voz (local)
- `sounddevice` - Grabación de audio
- `soundfile` - Procesamiento de audio
- `pytesseract` - OCR
- `pillow` - Procesamiento de imágenes
- `requests` - HTTP
- `python-dotenv` - Configuración
- Y más...

---

### Paso 4: Instalar Playwright (Navegadores)

```powershell
python -m playwright install chromium
```

Esto descarga el navegador Chromium (~200 MB).

---

### Paso 5: Instalar Tesseract OCR (Para Imágenes)

**Windows:**
1. Descargar de: https://github.com/UB-Mannheim/tesseract/wiki
2. Ejecutar instalador `tesseract-ocr-w64-setup-5.x.x.exe`
3. Instalar en ruta por defecto: `C:\Program Files\Tesseract-OCR`
4. Verificar:
```powershell
tesseract --version
# Debe mostrar: tesseract 5.x.x
```

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-spa
```

---

### Paso 6: Descargar Modelo de Whisper (Para Voz)

```powershell
# Descargar modelo base (primera vez)
python -c "import whisper; whisper.load_model('base')"
```

**Modelos disponibles:**
- `tiny` - 39 MB, más rápido, menos preciso
- `base` - 74 MB, balance (recomendado) ✅
- `small` - 244 MB, más preciso
- `medium` - 769 MB, muy preciso
- `large` - 1550 MB, máxima precisión

---

### Paso 7: Configurar `config.env`

```powershell
# El archivo ya existe, verificar configuración
notepad config.env
```

**Configuración recomendada:**
```env
# ─── Configuración General ───
OUTPUT_DIR=./output
TIMEOUT=60
HEADLESS=false              # false = ver navegador (recomendado)

# ─── OCR (Extracción de imágenes) ───
USE_OCR=true

# ─── reCAPTCHA ───
RECAPTCHA_AUTO=false        # false = semiautomático (gratis)

# ─── 2captcha (Opcional) ───
CAPTCHA_API_KEY=            # Dejar vacío si usas modo semiautomático

# ─── IMAP (Opcional - para NSS automático) ───
IMAP_EMAIL=
IMAP_PASSWORD=
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

# ─── Seguridad ───
STORAGE_KEY=cambia_esta_clave_secreta_32chars!
```

---

### Paso 8: Verificar Instalación

```powershell
python verificar_sistema.py
```

**Salida esperada:**
```
✅ Python 3.10+ instalado
✅ Playwright instalado
✅ Tesseract OCR disponible
✅ Whisper disponible
✅ Todas las dependencias instaladas
🎉 Sistema listo para usar!
```

---

## 🎤 Configuración de Entrada por Voz

### Windows

1. **Verificar micrófono:**
   - Configuración → Sistema → Sonido
   - Verificar que el micrófono esté activo

2. **Probar grabación:**
```powershell
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### macOS

1. **Dar permisos al Terminal:**
   - Preferencias del Sistema → Seguridad y Privacidad → Micrófono
   - Activar Terminal/iTerm

### Linux

```bash
sudo apt install portaudio19-dev
```

---

## 📷 Configuración de Entrada por Imagen

### Opción 1: Usar Archivos de Imagen

No requiere configuración adicional. Puedes usar fotos existentes.

### Opción 2: Captura desde Cámara (Futuro)

Actualmente en desarrollo. Por ahora usa archivos de imagen.

---

## 🧪 Pruebas del Sistema

### Test 1: Verificar Módulos Existentes

```powershell
# Test CURP
python test_curp_fix.py

# Test NSS
python test_nss.py
```

### Test 2: Probar Entrada por Voz

```powershell
python -c "from utils.voice_input import test_voice_input; test_voice_input()"
```

### Test 3: Probar OCR

```powershell
python -c "from utils.ocr import OCRExtractor; ocr = OCRExtractor(); print('OCR OK')"
```

---

## 🚀 Uso del Sistema

### Opción 1: Modo Interactivo (Recomendado)

```powershell
python main_multimodal.py
```

**Menú:**
```
  Trámites disponibles:
  1) CURP - Consulta y descarga
  2) NSS - Número de Seguridad Social
  3) Antecedentes No Penales
  4) Tenencia Vehicular
  5) CURP + NSS (ambos)
  6) Salir

  Selecciona opción: 1

  Modo de entrada:
  1) Texto (teclado)
  2) Voz (micrófono)
  3) Imagen (foto/archivo)
  
  Modo: 2
```

### Opción 2: Modo Directo con Texto

```powershell
# CURP
python main_multimodal.py --tramite curp

# NSS
python main_multimodal.py --tramite nss

# Antecedentes
python main_multimodal.py --tramite antecedentes

# Tenencia
python main_multimodal.py --tramite tenencia

# CURP + NSS
python main_multimodal.py --tramite ambos
```

### Opción 3: Modo Directo con Voz

```powershell
# CURP por voz
python main_multimodal.py --tramite curp --voice

# NSS por voz
python main_multimodal.py --tramite nss --voice
```

---

## 📊 Ejemplos de Uso

### Ejemplo 1: CURP con Entrada por Texto

```powershell
python main_multimodal.py --tramite curp

# Sistema:
  CURP (18 caracteres): OOLL940914HMCRGS08
  
# Resultado:
  [CURP] ✅ Completado en 16.3s
  PDF descargado: output/CURP_OOLL940914HMCRGS08.pdf
  📄 PDF abierto automáticamente
```

### Ejemplo 2: NSS con Entrada por Voz

```powershell
python main_multimodal.py --tramite nss --voice

# Sistema:
  🎤 Voy a grabar tu CURP
  Grabando en 3... 2... 1...
  🔴 GRABANDO (8 segundos)...
  
# Usuario dice:
  "Mi CURP es O O L L nueve cuatro cero nueve uno cuatro H M C R G S cero ocho"
  
# Sistema:
  ✅ CURP detectada: OOLL940914HMCRGS08
  
  🎤 Voy a grabar tu correo electrónico
  
# Usuario dice:
  "juan punto perez arroba gmail punto com"
  
# Sistema:
  ✅ Email detectado: juan.perez@gmail.com
  
  [NSS] 🔵 Modo SEMIAUTOMÁTICO activado
  [NSS] 👉 Resuelve el reCAPTCHA manualmente
  [NSS] ✅ reCAPTCHA resuelto en 8s
  [NSS] NSS encontrado: 12345678901
```

### Ejemplo 3: Tenencia con Entrada por Imagen

```powershell
python main_multimodal.py --tramite tenencia

# Sistema:
  Modo de entrada:
  1) Texto
  2) Voz
  3) Imagen
  
  Modo: 3
  
  Ruta de imagen de tarjeta de circulación: C:\Users\Juan\tarjeta.jpg
  
# Sistema extrae:
  [OCR] Placa detectada: ABC1234
  [TENENCIA] Consultando tenencia para placa ABC1234
  [TENENCIA] Monto: $1,250.00
  [TENENCIA] Formato descargado: output/Tenencia_ABC1234_2026.pdf
```

---

## 🔧 Solución de Problemas

### Error: "Whisper no está instalado"

**Solución:**
```powershell
pip install openai-whisper sounddevice soundfile
```

### Error: "Tesseract no encontrado"

**Solución:**
1. Instalar Tesseract desde: https://github.com/UB-Mannheim/tesseract/wiki
2. Verificar que esté en PATH
3. Reiniciar terminal

### Error: "No se detecta micrófono"

**Solución:**
```powershell
# Listar dispositivos de audio
python -c "import sounddevice as sd; print(sd.query_devices())"

# Verificar permisos del sistema
```

### Error: "ModuleNotFoundError"

**Solución:**
```powershell
pip install -r requirements.txt
```

### El navegador no se abre

**Solución:**
```powershell
python -m playwright install chromium
```

---

## 📈 Optimización del Sistema

### Para Máxima Velocidad

```env
# config.env
HEADLESS=true               # Ocultar navegador
USE_OCR=false              # Desactivar OCR si no es necesario
```

**Modelo de voz ligero:**
```python
# Usar modelo tiny en lugar de base
orchestrator = TramitesOrchestrator(voice_model="tiny")
```

### Para Máxima Precisión

```env
HEADLESS=false             # Ver navegador
USE_OCR=true               # Activar OCR
```

**Modelo de voz preciso:**
```python
orchestrator = TramitesOrchestrator(voice_model="small")
```

---

## 💰 Costos

### Modo Gratuito (Recomendado)

```env
RECAPTCHA_AUTO=false       # Semiautomático
```

**Costo total:** $0 USD

### Modo Automático (Opcional)

```env
RECAPTCHA_AUTO=true
CAPTCHA_API_KEY=tu_api_key
```

**Costos:**
- reCAPTCHA v2: ~$0.002 USD
- Imagen CAPTCHA: ~$0.001 USD

**Costo por trámite:** $0.001-0.004 USD

---

## 📚 Documentación Adicional

- `ANALISIS_TRAMITES_GOB_MX.md` - Análisis de portales
- `NUEVAS_FUNCIONALIDADES.md` - OCR y reCAPTCHA
- `RESUMEN_FINAL_COMPLETO.md` - Estado del sistema
- `GUIA_COMPLETA.md` - Documentación técnica

---

## ✅ Checklist de Instalación

- [ ] Python 3.10+ instalado
- [ ] Dependencias instaladas (`pip install -r requirements.txt`)
- [ ] Playwright instalado (`python -m playwright install chromium`)
- [ ] Tesseract OCR instalado
- [ ] Modelo Whisper descargado
- [ ] `config.env` configurado
- [ ] Sistema verificado (`python verificar_sistema.py`)
- [ ] Micrófono funcionando (para voz)
- [ ] Tests ejecutados exitosamente

---

## 🎉 ¡Listo!

El sistema está completamente instalado y configurado. Ahora puedes:

1. **Ejecutar trámites por texto:**
   ```powershell
   python main_multimodal.py --tramite curp
   ```

2. **Ejecutar trámites por voz:**
   ```powershell
   python main_multimodal.py --tramite nss --voice
   ```

3. **Modo interactivo:**
   ```powershell
   python main_multimodal.py
   ```

**¡Disfruta de la automatización de trámites gubernamentales!** 🚀
