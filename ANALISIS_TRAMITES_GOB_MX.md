# 📋 Análisis Exhaustivo de Trámites Gubernamentales de México
## Factibilidad de Automatización con IA Local y Entrada Multimodal

**Fecha de Análisis:** 17 de Marzo, 2026  
**Objetivo:** Evaluar la viabilidad técnica de automatizar trámites gubernamentales mexicanos con IA local, reduciendo tiempos de 10-25 minutos a menos de 2 minutos.

---

## 🎯 Resumen Ejecutivo

### Trámites Identificados en servicios.js (Categoría Administrativos)

| ID | Trámite | Precio Base | Factibilidad | Tiempo Estimado |
|---|---|---|---|---|
| `adm-nss-consulta` | Consulta y recuperación de NSS | $40 | ✅ **ALTA** | 30-60 seg |
| `adm-curp-consulta-correccion` | Consulta y apoyo CURP | $20 | ✅ **ALTA** | 15-25 seg |
| `adm-antecedentes-no-penales` | Antecedentes no penales | $80 | ✅ **ALTA** | 45-90 seg |
| `adm-semanas-cotizadas-imss` | Semanas cotizadas IMSS | $160 | 🟡 **MEDIA** | 60-120 seg |
| `adm-cita-ine` | Agendado de cita INE | $50 | 🟡 **MEDIA** | 30-60 seg |
| `adm-cita-rfc-sat` | Agendado de cita RFC SAT | $180 | 🟡 **MEDIA** | 45-90 seg |
| `adm-rfc-constancia-fiscal` | Descarga RFC y constancia | $480 | 🟢 **MEDIA-ALTA** | 60-90 seg |
| `adm-cita-pasaporte` | Agendado cita pasaporte | $180 | 🟡 **MEDIA** | 45-90 seg |
| `adm-cita-licencia` | Agendado cita licencia | $160 | 🟡 **MEDIA** | 30-60 seg |
| `adm-pago-tenencia-apoyo` | Apoyo pago tenencia | $35 | ✅ **ALTA** | 20-40 seg |

---

## 📊 Análisis Detallado por Trámite

### 1. ✅ CURP - Consulta y Descarga
**Portal:** https://consultas.curp.gob.mx/CurpSP/

#### Información del Trámite
- **Dependencia:** RENAPO (Registro Nacional de Población)
- **Modalidad:** En línea, gratuito
- **Requisitos:** Solo CURP de 18 caracteres
- **Costo:** $0 MXN
- **Tiempo oficial:** 5-10 minutos manual
- **Tiempo automatizado:** 15-25 segundos ✅

#### Estructura Técnica
```
✅ Formulario HTML simple
✅ CAPTCHA de imagen numérica (OCR o manual)
✅ Sin autenticación requerida
✅ PDF descargable directamente
✅ Sin APIs públicas (scraping necesario)
```

#### Factibilidad de Automatización
**🟢 ALTA - 95%**

**Entrada Multimodal:**
- ✅ **Texto:** CURP de 18 caracteres
- ✅ **Voz:** "Mi CURP es A B C D 1 2 3 4 5 6..." → Reconocimiento de voz → Texto
- ✅ **Imagen:** Foto de credencial/documento → OCR → Extracción de CURP

**Implementación:**
```python
# Ya implementado en modules/curp.py
# Características:
# - 20+ selectores alternativos
# - OCR integrado para extracción
# - PDF oficial descargado
# - Apertura automática
```

**Estado:** ✅ **YA IMPLEMENTADO Y FUNCIONAL**

---

### 2. ✅ NSS - Número de Seguridad Social IMSS
**Portal:** https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS

#### Información del Trámite
- **Dependencia:** IMSS (Instituto Mexicano del Seguro Social)
- **Modalidad:** En línea, gratuito
- **Requisitos:** 
  - CURP (18 caracteres)
  - Correo electrónico
- **Costo:** $0 MXN
- **Tiempo oficial:** 10-20 minutos manual
- **Tiempo automatizado:** 30-60 segundos ✅

#### Estructura Técnica
```
✅ Formulario web estructurado
🟡 reCAPTCHA v2 (semiautomático o 2captcha)
✅ Sin autenticación previa
✅ Respuesta por correo electrónico
🟡 Requiere lectura de correo (IMAP)
✅ Sin APIs públicas
```

#### Factibilidad de Automatización
**🟢 ALTA - 90%**

**Entrada Multimodal:**
- ✅ **Texto:** CURP + Correo
- ✅ **Voz:** "Mi CURP es... mi correo es..." → Reconocimiento → Texto
- ✅ **Imagen:** Foto de CURP → OCR → Extracción

**Implementación:**
```python
# Ya implementado en modules/nss.py
# Características:
# - reCAPTCHA semiautomático (gratis)
# - OCR para extracción de NSS
# - Lectura automática de correo IMAP
# - Logs detallados
```

**Estado:** ✅ **YA IMPLEMENTADO Y FUNCIONAL**

---

### 3. ✅ Antecedentes No Penales (Federal)
**Portal:** https://constancias.oadprs.gob.mx/

#### Información del Trámite
- **Dependencia:** OADPRS (Órgano Administrativo Desconcentrado Prevención y Readaptación Social)
- **Modalidad:** En línea
- **Requisitos:**
  - CURP
  - Correo electrónico
  - Crear cuenta (primera vez)
- **Costo:** Variable por estado ($0-$300 MXN)
- **Plazo:** Inmediato (descarga digital)
- **Documento:** PDF válido impreso en hoja blanca
- **Tiempo oficial:** 10-30 minutos manual
- **Tiempo automatizado:** 45-90 segundos ⏱️

#### Estructura Técnica
```
🟡 Requiere registro de cuenta
✅ Formulario web estándar
🟡 reCAPTCHA v2
✅ Descarga directa de PDF
✅ Válido ante autoridades
❌ Sin API pública
```

#### Factibilidad de Automatización
**🟢 ALTA - 85%**

**Entrada Multimodal:**
- ✅ **Texto:** CURP + Correo + Datos personales
- ✅ **Voz:** Dictado de datos → Reconocimiento → Formulario
- ✅ **Imagen:** Foto de INE/Credencial → OCR → Extracción de datos

**Flujo de Automatización:**
```
1. Verificar si existe cuenta (guardar credenciales localmente)
2. Si no existe: Crear cuenta automáticamente
3. Login automático
4. Llenar formulario con datos extraídos
5. Resolver reCAPTCHA (semiautomático)
6. Descargar PDF
7. Abrir automáticamente
```

**Requisitos Técnicos:**
- Playwright para navegación
- OCR para extracción de datos de credencial
- reCAPTCHA semiautomático (modo manual gratuito)
- Almacenamiento seguro de credenciales (encriptado)

**Estado:** ⏳ **PENDIENTE DE IMPLEMENTAR**

---

### 4. 🟡 Tenencia Vehicular - Estado de México
**Portal:** https://sfpya.edomexico.gob.mx/

#### Información del Trámite
- **Dependencia:** Secretaría de Finanzas del Estado de México
- **Modalidad:** En línea (consulta y pago)
- **Requisitos:**
  - Número de placa
  - Número de serie (VIN) o NIV
- **Costo:** Variable según vehículo ($500-$5,000+ MXN)
- **Formas de pago:** Tarjeta, referencia bancaria, tiendas
- **Plazo:** Inmediato (formato de pago)
- **Documento:** Formato de pago PDF
- **Tiempo oficial:** 10-20 minutos manual
- **Tiempo automatizado:** 20-40 segundos ⏱️

#### Estructura Técnica
```
✅ Portal web público
✅ Consulta sin autenticación
✅ Formulario simple (placa + serie)
🟡 CAPTCHA variable
✅ Generación de línea de captura
✅ PDF descargable
❌ Sin API pública
```

#### Factibilidad de Automatización
**🟢 ALTA - 90%**

**Entrada Multimodal:**
- ✅ **Texto:** Placa + Número de serie
- ✅ **Voz:** "Mi placa es A B C 1 2 3 4" → Reconocimiento
- ✅ **Imagen:** Foto de tarjeta de circulación → OCR → Extracción

**Flujo de Automatización:**
```
1. Navegar a portal de tenencia
2. Ingresar placa (voz/texto/imagen)
3. Ingresar número de serie (voz/texto/imagen)
4. Resolver CAPTCHA si existe
5. Generar formato de pago
6. Descargar PDF
7. Abrir automáticamente
8. Opcional: Mostrar opciones de pago
```

**Estado:** ⏳ **PENDIENTE DE IMPLEMENTAR**

---

### 5. 🟡 Semanas Cotizadas IMSS
**Portal:** https://serviciosdigitales.imss.gob.mx/

#### Información del Trámite
- **Dependencia:** IMSS
- **Modalidad:** En línea (requiere cuenta)
- **Requisitos:**
  - NSS
  - CURP
  - Correo electrónico
  - Cuenta IMSS Digital (registro previo)
- **Costo:** $0 MXN
- **Plazo:** Inmediato
- **Documento:** Reporte PDF de semanas cotizadas
- **Tiempo oficial:** 10-15 minutos manual
- **Tiempo automatizado:** 60-120 segundos ⏱️

#### Estructura Técnica
```
🟡 Requiere cuenta IMSS Digital
🟡 Autenticación con usuario/contraseña
✅ Portal web estructurado
🟡 Posible autenticación de dos factores
✅ Descarga de PDF
❌ Sin API pública
```

#### Factibilidad de Automatización
**🟡 MEDIA - 70%**

**Limitaciones:**
- Requiere cuenta previa (puede automatizarse el registro)
- Autenticación puede tener 2FA
- Sesión con timeout

**Entrada Multimodal:**
- ✅ **Texto:** NSS + CURP + Credenciales
- ✅ **Voz:** Dictado de datos
- ✅ **Imagen:** OCR de credencial IMSS

**Estado:** ⏳ **PENDIENTE - Requiere análisis de autenticación**

---

### 6. 🟡 Citas INE
**Portal:** https://citas.ine.mx/

#### Información del Trámite
- **Dependencia:** INE (Instituto Nacional Electoral)
- **Modalidad:** En línea (agendado de cita)
- **Requisitos:**
  - CURP
  - Correo electrónico
  - OCR (si es renovación)
  - Selección de módulo y horario
- **Costo:** $0 MXN (trámite presencial posterior)
- **Plazo:** Disponibilidad variable por módulo
- **Documento:** Confirmación de cita (PDF/correo)
- **Tiempo oficial:** 20-40 minutos manual (buscar disponibilidad)
- **Tiempo automatizado:** 30-60 segundos ⏱️

#### Estructura Técnica
```
✅ Portal web público
🟡 Sistema de disponibilidad en tiempo real
🟡 reCAPTCHA v3
✅ Formulario multi-paso
🟡 Selección de ubicación geográfica
✅ Confirmación por correo
❌ Sin API pública
```

#### Factibilidad de Automatización
**🟡 MEDIA - 75%**

**Desafíos:**
- Disponibilidad cambiante de citas
- Selección de módulo requiere preferencias del usuario
- reCAPTCHA v3

**Entrada Multimodal:**
- ✅ **Texto:** CURP + Preferencias de ubicación
- ✅ **Voz:** "Quiero cita en módulo de Toluca"
- ✅ **Imagen:** OCR de credencial anterior

**Estado:** ⏳ **PENDIENTE - Requiere lógica de búsqueda de disponibilidad**

---

## 🎤 Arquitectura de Entrada Multimodal

### 1. Entrada por Voz

**Tecnologías Locales:**
```python
# Opción 1: Whisper (OpenAI) - Local
import whisper

model = whisper.load_model("base")  # Modelos: tiny, base, small, medium, large
result = model.transcribe("audio.mp3", language="es")
texto = result["text"]

# Opción 2: Vosk (Offline, ligero)
from vosk import Model, KaldiRecognizer

model = Model("model-es")
rec = KaldiRecognizer(model, 16000)
# Procesar audio en tiempo real
```

**Flujo:**
```
Usuario dice: "Consulta mi CURP A B C D 1 2 3 4 5 6 H D F X X X 0 1"
       ↓
Whisper/Vosk transcribe
       ↓
Texto: "ABCD123456HDFXXX01"
       ↓
Validación de formato CURP
       ↓
Módulo de automatización
```

### 2. Entrada por Imagen

**Tecnologías Locales:**
```python
# Ya implementado en utils/ocr.py
from utils.ocr import OCRExtractor

ocr = OCRExtractor()

# Extraer de foto de credencial
data = ocr.extract_from_image("credencial.jpg")
curp = data["curp"]
nombre = data["nombre"]
```

**Flujo:**
```
Usuario toma foto de INE/Credencial
       ↓
OCR extrae texto
       ↓
Detecta: CURP, Nombre, Fecha de nacimiento
       ↓
Valida formato
       ↓
Módulo de automatización
```

### 3. Entrada por Texto

**Flujo Actual:**
```python
# Ya implementado
curp = input("Ingresa tu CURP: ")
correo = input("Ingresa tu correo: ")
```

---

## 🏗️ Arquitectura Propuesta del Sistema

### Componente 1: Interfaz Multimodal

```python
# modules/multimodal_input.py

class MultimodalInput:
    def __init__(self):
        self.ocr = OCRExtractor()
        self.voice = VoiceRecognizer()  # Whisper/Vosk
    
    def get_curp(self, mode="text"):
        """
        Obtiene CURP por texto, voz o imagen
        
        Args:
            mode: "text", "voice", "image"
        
        Returns:
            CURP validada
        """
        if mode == "text":
            return input("CURP: ").strip().upper()
        
        elif mode == "voice":
            print("🎤 Di tu CURP...")
            audio = self.voice.record()
            texto = self.voice.transcribe(audio)
            curp = self._extract_curp_from_text(texto)
            return curp
        
        elif mode == "image":
            print("📷 Toma foto de tu credencial...")
            imagen = self._capture_image()
            data = self.ocr.extract_from_image(imagen)
            return data["curp"]
```

### Componente 2: Orquestador de Trámites

```python
# modules/tramites_orchestrator.py

class TramitesOrchestrator:
    def __init__(self):
        self.curp_module = CURPModule(use_ocr=True)
        self.nss_module = NSSModule(use_ocr=True)
        self.antecedentes_module = AntecedentesModule()  # Nuevo
        self.tenencia_module = TenenciaModule()  # Nuevo
        self.multimodal = MultimodalInput()
    
    async def ejecutar_tramite(self, tipo, modo_entrada="text"):
        """
        Ejecuta trámite con entrada multimodal
        
        Args:
            tipo: "curp", "nss", "antecedentes", "tenencia", etc.
            modo_entrada: "text", "voice", "image"
        """
        if tipo == "curp":
            curp = self.multimodal.get_curp(mode=modo_entrada)
            return await self.curp_module.consultar(curp=curp)
        
        elif tipo == "nss":
            curp = self.multimodal.get_curp(mode=modo_entrada)
            correo = self.multimodal.get_email(mode=modo_entrada)
            return await self.nss_module.consultar(curp=curp, correo=correo)
```

### Componente 3: CLI con Comandos de Voz

```python
# main_voice.py

async def main_voice():
    orchestrator = TramitesOrchestrator()
    
    print("🎤 Sistema de Trámites por Voz")
    print("Di: 'consulta CURP', 'obtener NSS', 'antecedentes penales', etc.")
    
    while True:
        comando = voice.listen()  # Escucha continua
        
        if "curp" in comando.lower():
            await orchestrator.ejecutar_tramite("curp", modo_entrada="voice")
        
        elif "nss" in comando.lower() or "seguro social" in comando.lower():
            await orchestrator.ejecutar_tramite("nss", modo_entrada="voice")
        
        elif "salir" in comando.lower():
            break
```

---

## 📋 Módulos Pendientes de Implementar

### Prioridad Alta (Factibilidad 85%+)

1. **✅ Antecedentes No Penales**
   - Portal: https://constancias.oadprs.gob.mx/
   - Tiempo: 45-90 seg
   - Complejidad: Media (requiere cuenta)

2. **✅ Tenencia Vehicular**
   - Portal: https://sfpya.edomexico.gob.mx/
   - Tiempo: 20-40 seg
   - Complejidad: Baja

### Prioridad Media (Factibilidad 70-80%)

3. **🟡 Semanas Cotizadas IMSS**
   - Requiere cuenta IMSS Digital
   - Tiempo: 60-120 seg
   - Complejidad: Media-Alta

4. **🟡 Citas INE**
   - Búsqueda de disponibilidad
   - Tiempo: 30-60 seg
   - Complejidad: Media

5. **🟡 Citas RFC/SAT**
   - Similar a INE
   - Tiempo: 45-90 seg
   - Complejidad: Media

---

## 💰 Análisis de Costos

### Costos de Automatización

| Componente | Costo | Frecuencia |
|---|---|---|
| **Whisper (voz)** | $0 | Local |
| **OCR Tesseract** | $0 | Local |
| **Playwright** | $0 | Local |
| **reCAPTCHA manual** | $0 | Por trámite |
| **2captcha (opcional)** | $0.002 USD | Por CAPTCHA |
| **IMAP (correo)** | $0 | Gratis (Gmail) |
| **Total por trámite** | **$0** | Modo semiautomático |

### Comparación con Servicios Manuales

| Trámite | Precio Manual | Tiempo Manual | Costo Automatizado | Tiempo Auto |
|---|---|---|---|---|
| CURP | $20 | 5-10 min | $0 | 16 seg |
| NSS | $40 | 10-20 min | $0 | 30-60 seg |
| Antecedentes | $80 | 10-30 min | $0 | 45-90 seg |
| Tenencia | $35 | 10-20 min | $0 | 20-40 seg |

**Ahorro total:** $175 por conjunto de trámites  
**Ahorro de tiempo:** 35-80 min → 2-4 min (90% reducción)

---

## 🚀 Roadmap de Implementación

### Fase 1: Entrada Multimodal (2-3 días)
- [ ] Integrar Whisper para reconocimiento de voz
- [ ] Crear clase `MultimodalInput`
- [ ] Implementar captura de imagen desde cámara
- [ ] Validadores de datos por tipo de entrada

### Fase 2: Módulos Nuevos (1 semana)
- [ ] Módulo Antecedentes No Penales
- [ ] Módulo Tenencia Vehicular
- [ ] Módulo Semanas Cotizadas IMSS
- [ ] Módulo Citas INE

### Fase 3: Orquestador (2-3 días)
- [ ] Clase `TramitesOrchestrator`
- [ ] CLI con comandos de voz
- [ ] Gestión de perfiles multimodal

### Fase 4: Optimización (1 semana)
- [ ] Caché de datos frecuentes
- [ ] Modo batch (múltiples trámites)
- [ ] Dashboard de estado
- [ ] Logs y métricas

---

## ✅ Recomendaciones Finales

### Para Uso Local sin Costos

**Configuración Óptima:**
```env
# config.env
HEADLESS=false              # Ver navegador
USE_OCR=true                # OCR local (Tesseract)
RECAPTCHA_AUTO=false        # Modo semiautomático (gratis)
USE_VOICE=true              # Whisper local
VOICE_MODEL=base            # Modelo Whisper (tiny/base/small)
```

### Requisitos del Sistema

**Hardware Mínimo:**
- CPU: 4 cores
- RAM: 8 GB
- Disco: 10 GB libres
- Micrófono (para voz)
- Cámara web (para imágenes)

**Software:**
- Python 3.10+
- Tesseract OCR
- Whisper (pip install openai-whisper)
- Playwright
- Dependencias actuales

### Instalación Completa

```powershell
# 1. Dependencias Python
pip install -r requirements.txt
pip install openai-whisper
pip install vosk  # Alternativa ligera

# 2. Tesseract OCR
# Descargar de: https://github.com/UB-Mannheim/tesseract/wiki

# 3. Playwright
python -m playwright install chromium

# 4. Modelo Whisper (primera vez)
python -c "import whisper; whisper.load_model('base')"
```

---

## 📊 Matriz de Factibilidad Final

| Trámite | Factibilidad | Tiempo | Entrada Voz | Entrada Imagen | Estado |
|---|---|---|---|---|---|
| CURP | 🟢 95% | 16s | ✅ | ✅ | Implementado |
| NSS | 🟢 90% | 30-60s | ✅ | ✅ | Implementado |
| Antecedentes | 🟢 85% | 45-90s | ✅ | ✅ | Pendiente |
| Tenencia | 🟢 90% | 20-40s | ✅ | ✅ | Pendiente |
| Semanas IMSS | 🟡 70% | 60-120s | ✅ | ✅ | Pendiente |
| Cita INE | 🟡 75% | 30-60s | ✅ | ✅ | Pendiente |
| Cita RFC | 🟡 75% | 45-90s | ✅ | ✅ | Pendiente |

**Leyenda:**
- 🟢 Alta (85%+): Implementación directa
- 🟡 Media (70-84%): Requiere análisis adicional
- 🔴 Baja (<70%): No recomendado

---

## 🎯 Conclusión

**Es completamente factible** automatizar los trámites gubernamentales mexicanos de forma local con las siguientes características:

✅ **Sin costos recurrentes** (modo semiautomático)  
✅ **Entrada multimodal** (voz, imagen, texto)  
✅ **Reducción de tiempo del 90%+**  
✅ **Ejecución local** (sin dependencias cloud)  
✅ **OCR integrado** para extracción de datos  
✅ **reCAPTCHA semiautomático** (gratis)  

**Próximo paso:** Implementar módulos pendientes siguiendo la arquitectura propuesta.
