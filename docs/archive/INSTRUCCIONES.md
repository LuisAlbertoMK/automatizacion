# 🤖 Sistema de Automatización de Trámites GOB.MX

## ✅ Cambios Realizados

He corregido el error del módulo CURP. Los cambios incluyen:

1. **Reorganización de archivos** - Creé las carpetas `utils/` y `modules/` necesarias
2. **Selectores mejorados** - Actualicé los selectores CSS para que funcionen con el portal actual
3. **Mejor manejo de errores** - Agregué logs de debug y múltiples estrategias de búsqueda
4. **Screenshots automáticos** - El sistema guarda `debug_portal.png` para depuración

## 🔧 Instalación de Dependencias

Antes de ejecutar el sistema, instala las dependencias:

```powershell
# Instalar paquetes de Python
pip install -r requirements.txt

# Instalar navegadores de Playwright (IMPORTANTE)
python -m playwright install chromium
```

## 🚀 Cómo Probar el Sistema

### Opción 1: Modo Interactivo (Recomendado para pruebas)

```powershell
python main.py
```

Luego escribe `curp` y proporciona el CURP: `OOLL940914HMCRGS08`

### Opción 2: Modo Directo

```powershell
python main.py --tramite curp --curp OOLL940914HMCRGS08
```

### Opción 3: Script de Prueba

```powershell
python test_curp_fix.py
```

## 🐛 Depuración

El sistema ahora incluye **modo debug** que:

- Muestra el navegador (HEADLESS=false en config.env)
- Imprime todos los inputs encontrados
- Guarda screenshots en `debug_portal.png`
- Muestra qué selectores están funcionando

### Ver el navegador durante la ejecución

Edita `config.env` y cambia:
```
HEADLESS=false
```

## 📋 Próximos Pasos

1. **Probar CURP** - Ejecuta una prueba con tu CURP
2. **Revisar screenshot** - Si falla, revisa `debug_portal.png` 
3. **Ajustar selectores** - Si el portal cambió, los logs te dirán qué inputs están disponibles
4. **Configurar 2captcha** (opcional) - Para resolver CAPTCHAs automáticamente
5. **Probar NSS** - Una vez que CURP funcione

## 🔍 Diagnóstico del Error Actual

El error "No se encontró el campo de CURP" ocurría porque:

- Los selectores CSS no coincidían con la estructura actual del portal
- El portal puede tener diferentes versiones/URLs
- No había suficiente tiempo de espera para que cargue la página

**Solución implementada:**

- ✅ Múltiples selectores alternativos
- ✅ Detección automática de campos visibles
- ✅ Logs detallados para depuración
- ✅ Fallback a URLs alternativas del portal
- ✅ Screenshots automáticos

## 📊 Métricas Objetivo (según tu imagen)

- **CURP**: 5-10 min manual → **15-25 seg auto** (Alta prioridad - 88%)
- **NSS**: 10-20 min manual → **30-60 seg auto** (Alta prioridad - 82%)

## ⚠️ Notas Importantes

1. El portal de GOB.MX puede cambiar su estructura HTML
2. Los CAPTCHAs serán manuales sin una API key de 2captcha
3. El sistema es **semiautomático**: llena todo, tú solo confirmas
4. Revisa los logs de debug si algo falla

## 🆘 Si Algo Falla

1. Verifica que Playwright esté instalado: `python -m playwright install`
2. Revisa `debug_portal.png` para ver qué ve el navegador
3. Ejecuta con `HEADLESS=false` para ver el proceso en vivo
4. Revisa los logs de debug que muestran todos los inputs encontrados
