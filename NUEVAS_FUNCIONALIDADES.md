# 🆕 Nuevas Funcionalidades - OCR y reCAPTCHA Semiautomático

## 📋 Resumen

Se han implementado dos funcionalidades clave para mejorar la automatización:

1. **OCR (Reconocimiento Óptico de Caracteres)** - Extrae texto de imágenes y PDFs
2. **reCAPTCHA Semiautomático** - Espera resolución manual sin necesidad de 2captcha

---

## 🔍 1. OCR - Extracción de Texto de Imágenes

### ¿Qué es?

El OCR permite extraer texto de imágenes, screenshots y PDFs usando Tesseract. Esto mejora significativamente la extracción de datos cuando el HTML no contiene la información.

### Instalación

```powershell
# Instalar dependencias de Python
pip install pytesseract pillow pdf2image

# Descargar e instalar Tesseract OCR
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# Descargar el instalador y ejecutarlo
```

### Configuración

En `config.env`:
```env
USE_OCR=true
```

### Funcionalidades

**Extracción Automática:**
- ✅ CURP de imágenes y PDFs
- ✅ NSS de screenshots
- ✅ RFC de documentos
- ✅ Fechas, emails, teléfonos
- ✅ Nombres y datos personales

**Uso en Módulos:**

```python
from modules.curp import CURPModule

# OCR activado por defecto
modulo = CURPModule(use_ocr=True)
resultado = await modulo.consultar(curp="OOLL940914HMCRGS08")

# Si el HTML no contiene el nombre, el OCR lo extraerá del screenshot
```

**Uso Directo del OCR:**

```python
from utils.ocr import OCRExtractor

ocr = OCRExtractor()

# Extraer de imagen
texto = ocr.extract_from_image("screenshot.png")

# Extraer de PDF
texto = ocr.extract_from_pdf("documento.pdf")

# Extraer datos específicos
data = ocr.extract_all_data(texto)
print(data["curp"])  # CURP encontrada
print(data["nss"])   # NSS encontrado
print(data["email"]) # Email encontrado
```

### Casos de Uso

1. **CURP:** Si el portal cambia y el HTML no contiene los datos, el OCR los extrae del screenshot
2. **NSS:** Extrae el NSS de la página de resultados aunque no esté en el HTML
3. **PDFs:** Extrae información de PDFs escaneados o imágenes

### Preprocesamiento de Imágenes

El OCR incluye preprocesamiento automático para mejorar la precisión:
- Conversión a escala de grises
- Aumento de contraste (2x)
- Aumento de nitidez
- Redimensionamiento inteligente

---

## 🤖 2. reCAPTCHA Semiautomático

### ¿Qué es?

El modo semiautomático permite que el usuario resuelva los reCAPTCHAs manualmente en el navegador, sin necesidad de pagar por 2captcha. El sistema espera hasta que el CAPTCHA esté resuelto.

### Configuración

En `config.env`:
```env
# Modo semiautomático (por defecto)
RECAPTCHA_AUTO=false

# Modo automático (requiere 2captcha)
RECAPTCHA_AUTO=true
```

### Cómo Funciona

**Modo Semiautomático (RECAPTCHA_AUTO=false):**

1. El sistema detecta el reCAPTCHA
2. Muestra mensaje: "🔵 Modo SEMIAUTOMÁTICO activado"
3. Muestra instrucción: "👉 Resuelve el reCAPTCHA manualmente en el navegador"
4. Espera hasta 120 segundos
5. Verifica cada 2 segundos si fue resuelto
6. Continúa automáticamente cuando detecta que está resuelto

**Modo Automático (RECAPTCHA_AUTO=true):**

1. El sistema detecta el reCAPTCHA
2. Envía a 2captcha para resolución automática
3. Espera 15-45 segundos
4. Inyecta el token automáticamente
5. Continúa el proceso

### Ventajas del Modo Semiautomático

✅ **Sin costo** - No necesitas pagar por 2captcha  
✅ **Confiable** - Tú resuelves el CAPTCHA, 100% de éxito  
✅ **Rápido** - Resuelves en 5-10 segundos vs 15-45 seg de 2captcha  
✅ **Flexible** - Puedes cambiar entre modos fácilmente  

### Ejemplo de Uso

**NSS con reCAPTCHA Semiautomático:**

```powershell
# 1. Ejecutar el módulo
python main.py

# 2. Seleccionar NSS
tramites> nss

# 3. Ingresar datos
CURP: OOLL940914HMCRGS08
Correo: tucorreo@gmail.com

# 4. El navegador se abre
# 5. Aparece mensaje:
#    🔵 Modo SEMIAUTOMÁTICO activado
#    👉 Resuelve el reCAPTCHA manualmente en el navegador
#    ⏱️  Esperando hasta 120 segundos...

# 6. Resuelves el reCAPTCHA en el navegador
# 7. El sistema detecta automáticamente que está resuelto
# 8. Continúa el proceso automáticamente
```

### Indicadores Visuales

Durante la espera, verás:
```
[NSS] 🔵 Modo SEMIAUTOMÁTICO activado
[NSS] 👉 Resuelve el reCAPTCHA manualmente en el navegador
[NSS] ⏱️  Esperando hasta 120 segundos...
[NSS] ⏳ Esperando... (10s/120s)
[NSS] ⏳ Esperando... (20s/120s)
[NSS] ✅ reCAPTCHA resuelto en 8s
```

### Timeout

Si no resuelves el CAPTCHA en 120 segundos:
```
[NSS] ⚠ Timeout: reCAPTCHA no resuelto en 120s
[NSS] Continuando de todas formas...
```

El sistema intentará continuar de todas formas, pero puede fallar si el CAPTCHA es obligatorio.

---

## 🔧 Configuración Completa

### config.env Actualizado

```env
# ─── 2captcha (Opcional - solo si quieres modo automático) ───
CAPTCHA_API_KEY=tu_api_key_aqui

# ─── Correo IMAP (Opcional - para NSS automático) ───
IMAP_EMAIL=tucorreo@gmail.com
IMAP_PASSWORD=tu_contrasena_de_aplicacion
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

# ─── Configuración General ───
OUTPUT_DIR=./output
TIMEOUT=60
HEADLESS=false  # false = ver navegador (recomendado para semiautomático)

# ─── OCR (Extracción de texto de imágenes) ───
USE_OCR=true

# ─── reCAPTCHA ───
# false = semiautomático (gratis, resuelves manualmente)
# true = automático (requiere 2captcha, costo ~$0.002 USD)
RECAPTCHA_AUTO=false

# Clave para encriptar perfiles
STORAGE_KEY=cambia_esta_clave_secreta_32chars!
```

---

## 📊 Comparación de Modos

### reCAPTCHA

| Aspecto | Semiautomático | Automático |
|---------|----------------|------------|
| **Costo** | Gratis | ~$0.002 USD |
| **Tiempo** | 5-10 seg | 15-45 seg |
| **Precisión** | 100% | ~95% |
| **Requiere** | Atención manual | 2captcha API |
| **Mejor para** | Uso personal | Automatización masiva |

### OCR

| Aspecto | Sin OCR | Con OCR |
|---------|---------|---------|
| **Extracción** | Solo HTML | HTML + Imágenes |
| **Robustez** | Media | Alta |
| **Datos** | Limitados | Completos |
| **Requiere** | Nada | Tesseract |
| **Mejor para** | Portales estables | Portales cambiantes |

---

## 🎯 Casos de Uso Recomendados

### Uso Personal (Recomendado)

```env
HEADLESS=false
USE_OCR=true
RECAPTCHA_AUTO=false
```

**Ventajas:**
- Sin costos adicionales
- Ves el proceso en vivo
- Resuelves CAPTCHAs manualmente (más rápido)
- OCR como respaldo

### Automatización Masiva

```env
HEADLESS=true
USE_OCR=true
RECAPTCHA_AUTO=true
CAPTCHA_API_KEY=tu_api_key
```

**Ventajas:**
- Completamente automático
- No requiere intervención
- Ideal para procesar múltiples trámites

### Debug/Desarrollo

```env
HEADLESS=false
USE_OCR=true
RECAPTCHA_AUTO=false
```

**Ventajas:**
- Ves exactamente qué pasa
- OCR muestra qué texto extrae
- Control total del proceso

---

## 🧪 Pruebas

### Probar OCR

```python
from utils.ocr import OCRExtractor

ocr = OCRExtractor()

# Probar con una imagen
texto = ocr.extract_from_image("test_image.png")
print(texto)

# Extraer CURP
curp = ocr.extract_curp(texto)
print(f"CURP: {curp}")
```

### Probar reCAPTCHA Semiautomático

```powershell
# 1. Configurar modo semiautomático
# En config.env: RECAPTCHA_AUTO=false

# 2. Ejecutar NSS
python main.py

# 3. Seleccionar NSS y seguir instrucciones
tramites> nss

# 4. Cuando aparezca el reCAPTCHA, resuélvelo manualmente
# 5. El sistema continuará automáticamente
```

---

## 📝 Notas Importantes

### OCR

1. **Tesseract requerido:** Debes instalar Tesseract OCR en tu sistema
2. **Idioma:** Configurado para español por defecto (`lang='spa'`)
3. **Precisión:** Depende de la calidad de la imagen
4. **Preprocesamiento:** Automático para mejorar resultados

### reCAPTCHA Semiautomático

1. **HEADLESS=false:** Debes ver el navegador para resolver el CAPTCHA
2. **Timeout:** 120 segundos por defecto
3. **Detección:** Verifica cada 2 segundos si fue resuelto
4. **Fallback:** Si falla, continúa de todas formas

---

## 🚀 Beneficios

### Con OCR

✅ Mayor robustez ante cambios en portales  
✅ Extracción de datos de PDFs escaneados  
✅ Respaldo cuando HTML no tiene información  
✅ Extracción de múltiples tipos de datos  

### Con reCAPTCHA Semiautomático

✅ Sin costos de 2captcha  
✅ Más rápido que 2captcha  
✅ 100% de precisión  
✅ Control total del proceso  
✅ Ideal para uso personal  

---

## 🔄 Migración

Si ya usabas el sistema, los cambios son **retrocompatibles**:

- OCR se activa automáticamente si está disponible
- reCAPTCHA usa modo semiautomático por defecto
- Puedes desactivar OCR con `USE_OCR=false`
- Puedes activar modo automático con `RECAPTCHA_AUTO=true`

No necesitas cambiar tu código existente.

---

## 📞 Soporte

Si tienes problemas:

1. **OCR no funciona:** Verifica que Tesseract esté instalado
2. **reCAPTCHA no detecta:** Asegúrate de que `HEADLESS=false`
3. **Timeout:** Aumenta el tiempo en el código si necesitas más de 120s

---

## ✨ Resumen

Estas dos funcionalidades hacen el sistema más **robusto**, **económico** y **flexible**:

- **OCR:** Extrae información que el HTML no proporciona
- **reCAPTCHA Semiautomático:** Elimina costos manteniendo la automatización

**Configuración recomendada para uso personal:**
```env
USE_OCR=true
RECAPTCHA_AUTO=false
HEADLESS=false
```

¡Disfruta de la automatización mejorada! 🎉
