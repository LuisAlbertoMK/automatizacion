# 🤖 Sistema de Automatización de Trámites GOB.MX - Guía Completa

## 📋 Índice
1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Módulos Disponibles](#módulos-disponibles)
3. [Instalación](#instalación)
4. [Configuración](#configuración)
5. [Uso](#uso)
6. [Métricas de Rendimiento](#métricas-de-rendimiento)
7. [Solución de Problemas](#solución-de-problemas)
8. [Arquitectura Técnica](#arquitectura-técnica)

---

## 📊 Resumen Ejecutivo

Sistema de automatización semiautomática para trámites gubernamentales mexicanos que reduce tiempos de **10-25 minutos a menos de 2 minutos** por trámite.

### ✅ Estado Actual

| Módulo | Estado | Tiempo Manual | Tiempo Auto | Reducción |
|--------|--------|---------------|-------------|-----------|
| **CURP** | ✅ Funcional | 5-10 min | 16 seg | 97% |
| **NSS IMSS** | ✅ Optimizado | 10-20 min | 30-60 seg | 90% |
| Antecedentes Penales | ⏳ Pendiente | 10-30 min | - | - |
| Tenencia Vehicular | ⏳ Pendiente | 10-20 min | - | - |
| Semanas Cotizadas | ⏳ Pendiente | 10-15 min | - | - |
| Cita INE | ⏳ Pendiente | 20-40 min | - | - |
| RFC/SAT | ⏳ Pendiente | 20-45 min | - | - |

---

## 🔧 Módulos Disponibles

### 1. CURP - Consulta y Descarga ✅
**Portal:** https://consultas.curp.gob.mx/CurpSP/

**Características:**
- ✅ Descarga PDF oficial (no screenshot)
- ✅ Apertura automática del documento
- ✅ Detección inteligente de campos
- ✅ 20+ selectores alternativos
- ✅ Logs detallados de debug
- ✅ Screenshots automáticos para depuración

**Uso:**
```python
from src.tramites.curp import CURPModule

modulo = CURPModule(captcha_solver=None)
resultado = await modulo.consultar(curp="OOLL940914HMCRGS08")
# Resultado: {'curp': 'OOLL940914HMCRGS08', 'nombre': '...', 'pdf_path': 'output/CURP_...pdf'}
```

**Tiempo:** 15-25 segundos

---

### 2. NSS - Número de Seguridad Social IMSS ✅
**Portal:** https://serviciosdigitales.imss.gob.mx/gestionAsegurados-web-externo/asignacionNSS

**Características:**
- ✅ Llenado automático de formulario
- ✅ Detección de reCAPTCHA v2
- ✅ Lectura automática de correo (opcional)
- ✅ Selectores robustos
- ✅ Logs de debug detallados

**Uso:**
```python
from src.tramites.nss import NSSModule

modulo = NSSModule(captcha_solver=None, mail_reader=None)
resultado = await modulo.consultar(
    curp="OOLL940914HMCRGS08",
    correo="tucorreo@gmail.com"
)
# Resultado: {'nss': '12345678901', 'curp': '...', 'correo': '...'}
```

**Tiempo:** 30-60 segundos (depende del correo del IMSS)

---

## 🚀 Instalación

### Paso 1: Instalar Dependencias de Python

```powershell
pip install -r requirements.txt
```

### Paso 2: Instalar Navegadores de Playwright

```powershell
python -m playwright install chromium
```

### Paso 3: Verificar Instalación

```powershell
python verificar_sistema.py
```

Deberías ver:
```
✅ Todas las dependencias están instaladas
✅ Playwright configurado
🎉 Sistema listo para usar!
```

---

## ⚙️ Configuración

### Archivo `config.env`

```env
# ─── 2captcha (Opcional - para CAPTCHAs automáticos) ───
CAPTCHA_API_KEY=tu_api_key_aqui

# ─── Correo IMAP (Opcional - para NSS automático) ───
IMAP_EMAIL=tucorreo@gmail.com
IMAP_PASSWORD=tu_contrasena_de_aplicacion
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

# ─── Configuración General ───
OUTPUT_DIR=./output
TIMEOUT=60
HEADLESS=false  # true = oculto, false = visible (recomendado para debug)
STORAGE_KEY=cambia_esta_clave_secreta_32chars!
```

### Configurar Gmail para IMAP (Opcional)

1. Ve a https://myaccount.google.com
2. Seguridad → Verificación en dos pasos (actívala)
3. Busca "Contraseñas de aplicaciones"
4. Genera una para "Correo / Windows"
5. Usa esa contraseña de 16 caracteres en `IMAP_PASSWORD`

### Configurar 2captcha (Opcional)

1. Regístrate en https://2captcha.com
2. Recarga $2-5 USD
3. Copia tu API key
4. Pégala en `CAPTCHA_API_KEY`

---

## 💻 Uso

### Modo 1: Interactivo (Recomendado)

```powershell
python main.py
```

Comandos disponibles:
- `curp` - Consultar CURP
- `nss` - Obtener NSS del IMSS
- `ambos` - CURP + NSS en una operación
- `perfil` - Gestionar perfiles guardados
- `ayuda` - Mostrar ayuda
- `salir` - Salir

### Modo 2: Directo (Scripts/Automatización)

```powershell
# Solo CURP
python main.py --tramite curp --curp OOLL940914HMCRGS08

# Solo NSS
python main.py --tramite nss --curp OOLL940914HMCRGS08 --correo correo@ejemplo.com

# Con perfil guardado
python main.py --tramite curp --perfil juan_garcia
```

### Modo 3: Scripts de Prueba

```powershell
# Probar CURP
python test_curp_fix.py

# Probar NSS
python test_nss.py
```

---

## 📊 Métricas de Rendimiento

### CURP
- **Tiempo manual:** 5-10 minutos
- **Tiempo automatizado:** 15-25 segundos
- **Reducción:** 97%
- **Prioridad:** Alta (88%)
- **Estado:** ✅ Completamente funcional

### NSS IMSS
- **Tiempo manual:** 10-20 minutos
- **Tiempo automatizado:** 30-60 segundos
- **Reducción:** 90%
- **Prioridad:** Alta (82%)
- **Estado:** ✅ Optimizado

### Objetivos Futuros

| Trámite | Tiempo Manual | Objetivo Auto | Prioridad |
|---------|---------------|---------------|-----------|
| Antecedentes Penales | 10-30 min | 30-60 seg | Media (62%) |
| Tenencia Vehicular | 10-20 min | 25-60 seg | Media (70%) |
| Semanas Cotizadas | 10-15 min | 45 seg | Alta (75%) |
| Cita INE | 20-40 min | 60-120 seg | Media (55%) |
| RFC/SAT | 20-45 min | 2-4 min | Media (50%) |

---

## 🔍 Solución de Problemas

### Error: "No se encontró el campo de CURP"

**Solución:**
1. Ejecuta con `HEADLESS=false` en `config.env`
2. Revisa el screenshot `debug_portal.png`
3. Verifica los logs de debug que muestran qué inputs se encontraron
4. El portal puede estar en mantenimiento

### Error: "Module not found"

**Solución:**
```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

### El PDF no se abre automáticamente

**Solución:**
- Verifica que tengas un visor de PDF instalado
- En Windows, el sistema usa el visor predeterminado
- El PDF se guarda en `output/CURP_*.pdf` de todas formas

### reCAPTCHA no se resuelve

**Solución:**
- Sin API de 2captcha: Resuélvelo manualmente cuando aparezca
- Con API de 2captcha: Verifica que tengas saldo suficiente
- El sistema espera 15-45 segundos para resolverlo

### No llega el correo del IMSS

**Solución:**
1. Verifica que el correo sea correcto
2. Revisa la carpeta de spam
3. El IMSS puede tardar 2-5 minutos en enviar el correo
4. Sin configuración IMAP, debes revisar manualmente

---

## 🏗️ Arquitectura Técnica

### Estructura del Proyecto

```
d:\proyectos\automatizacion\
├── main.py                    # CLI principal
├── config.env                 # Configuración
├── requirements.txt           # Dependencias
│
├── modules/                   # Módulos de trámites
│   ├── __init__.py
│   ├── curp.py               # ✅ CURP
│   └── nss.py                # ✅ NSS IMSS
│
├── utils/                     # Utilidades
│   ├── __init__.py
│   ├── captcha.py            # Cliente 2captcha
│   ├── storage.py            # Gestión de perfiles
│   └── mail_reader.py        # Lectura de correos IMAP
│
├── output/                    # PDFs descargados
│   └── CURP_*.pdf
│
└── docs/                      # Documentación
    ├── INSTRUCCIONES.md
    ├── CAMBIOS_REALIZADOS.md
    └── GUIA_COMPLETA.md
```

### Tecnologías Utilizadas

- **Playwright** - Automatización de navegador moderna y robusta
- **Python 3.10+** - Lenguaje base
- **2captcha** - Resolución de CAPTCHAs (opcional)
- **IMAP** - Lectura de correos (opcional)
- **Colorama** - Interfaz CLI colorida
- **Cryptography** - Encriptación de perfiles

### Características Técnicas

1. **Selectores Múltiples** - 10-20 selectores alternativos por campo
2. **Detección Inteligente** - Búsqueda automática de campos visibles
3. **Logs Detallados** - Debug completo de cada paso
4. **Screenshots Automáticos** - Evidencia visual del proceso
5. **Fallbacks Robustos** - URLs alternativas si la principal falla
6. **Manejo de Errores** - Mensajes claros y accionables
7. **Modo Semiautomático** - El agente llena todo, tú solo confirmas

### Flujo de Trabajo - CURP

```
1. Abrir portal CURP
2. Detectar y activar pestaña "Por CURP"
3. Llenar campo CURP (20+ selectores alternativos)
4. Detectar CAPTCHA (si existe)
5. Resolver CAPTCHA (2captcha o manual)
6. Enviar formulario
7. Extraer datos del resultado
8. Descargar PDF oficial (no screenshot)
9. Abrir PDF automáticamente
10. Retornar resultado
```

### Flujo de Trabajo - NSS

```
1. Abrir portal IMSS
2. Llenar campo CURP
3. Llenar campo correo
4. Detectar reCAPTCHA v2
5. Resolver reCAPTCHA (2captcha o manual)
6. Enviar formulario
7. Buscar NSS en respuesta de página
8. Si no está, esperar correo del IMSS
9. Leer correo automáticamente (IMAP)
10. Extraer NSS del correo
11. Retornar resultado
```

---

## 🎯 Próximos Pasos

### Corto Plazo
- [ ] Crear módulo de Antecedentes Penales
- [ ] Crear módulo de Tenencia Vehicular
- [ ] Crear módulo de Semanas Cotizadas IMSS
- [ ] Optimizar tiempos de espera
- [ ] Agregar más tests automatizados

### Mediano Plazo
- [ ] Crear módulo de Cita INE
- [ ] Crear módulo de RFC/SAT
- [ ] Implementar sistema de cola para múltiples trámites
- [ ] Dashboard web para monitoreo
- [ ] API REST para integración

### Largo Plazo
- [ ] Aplicación móvil
- [ ] Notificaciones push
- [ ] Integración con calendarios
- [ ] Sistema de recordatorios
- [ ] Exportación a diferentes formatos

---

## 📞 Soporte

Si encuentras problemas:

1. **Revisa los logs** - Muestran exactamente qué pasó
2. **Revisa screenshots** - `debug_portal.png`, `debug_nss_portal.png`
3. **Ejecuta con HEADLESS=false** - Ve el proceso en vivo
4. **Verifica dependencias** - `python verificar_sistema.py`
5. **Revisa la documentación** - `INSTRUCCIONES.md`, `CAMBIOS_REALIZADOS.md`

---

## 📄 Licencia

Sistema de automatización para uso personal. Respeta los términos de servicio de los portales gubernamentales.

---

## ✨ Créditos

Desarrollado para automatizar trámites gubernamentales mexicanos y reducir tiempos de espera de 10-25 minutos a menos de 2 minutos.

**Versión:** 1.0  
**Fecha:** Marzo 2026  
**Estado:** Producción (CURP y NSS funcionales)
