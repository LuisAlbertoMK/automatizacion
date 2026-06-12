#!/usr/bin/env python3
"""
verificar_sistema_completo.py
Verifica que todas las dependencias y componentes estén instalados correctamente
Incluye verificación de entrada multimodal (voz, imagen, texto)
"""

import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Verifica versión de Python."""
    print("\n📌 Verificando Python...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 10:
        print(f"  [OK] Python {version.major}.{version.minor}.{version.micro} instalado")
        return True
    else:
        print(f"  [ERR] Python {version.major}.{version.minor} - Se requiere 3.10+")
        return False

def check_module(module_name, package_name=None):
    """Verifica si un módulo de Python está instalado."""
    if package_name is None:
        package_name = module_name
    
    try:
        __import__(module_name)
        print(f"  [OK] {package_name} instalado")
        return True
    except ImportError:
        print(f"  [ERR] {package_name} NO instalado")
        print(f"     Instalar con: pip install {package_name}")
        return False

def check_playwright():
    """Verifica Playwright y navegadores."""
    print("\n📌 Verificando Playwright...")
    
    if not check_module("playwright"):
        return False
    
    # Verificar si chromium está instalado
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        print("  [OK] Chromium instalado")
        return True
    except Exception as e:
        print("  [ERR] Chromium NO instalado")
        print("     Instalar con: python -m playwright install chromium")
        return False

def check_tesseract():
    """Verifica Tesseract OCR."""
    print("\n📌 Verificando Tesseract OCR...")
    
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"  [OK] {version}")
            return True
        else:
            print("  [ERR] Tesseract NO encontrado")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  [ERR] Tesseract NO instalado")
        print("     Descargar de: https://github.com/UB-Mannheim/tesseract/wiki")
        return False

def check_whisper():
    """Verifica Whisper para reconocimiento de voz."""
    print("\n📌 Verificando Whisper (Voz)...")
    
    if not check_module("whisper", "openai-whisper"):
        return False
    
    # Verificar si el modelo base está descargado
    try:
        import whisper
        print("  [i]️  Verificando modelo 'base'...")
        model = whisper.load_model("base")
        print("  [OK] Modelo 'base' disponible")
        return True
    except Exception as e:
        print(f"  [!]️  Modelo 'base' no descargado")
        print("     Descargar con: python -c \"import whisper; whisper.load_model('base')\"")
        return True  # Whisper está instalado, solo falta el modelo

def check_audio_libs():
    """Verifica librerías de audio."""
    print("\n📌 Verificando librerías de audio...")
    
    all_ok = True
    all_ok &= check_module("sounddevice")
    all_ok &= check_module("soundfile")
    all_ok &= check_module("numpy")
    
    return all_ok

def check_project_structure():
    """Verifica estructura del proyecto."""
    print("\n📌 Verificando estructura del proyecto...")
    
    required_dirs = [
        "modules",
        "utils",
        "output",
    ]
    
    required_files = [
        "modules/curp.py",
        "modules/nss.py",
        "modules/antecedentes.py",
        "modules/tenencia.py",
        "modules/orchestrator.py",
        "utils/ocr.py",
        "utils/voice_input.py",
        "utils/multimodal_input.py",
        "utils/captcha.py",
        "main_multimodal.py",
        "config.env",
        "requirements.txt",
    ]
    
    all_ok = True
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"  [OK] Directorio {dir_name}/ existe")
        else:
            print(f"  [ERR] Directorio {dir_name}/ NO existe")
            all_ok = False
    
    for file_name in required_files:
        file_path = Path(file_name)
        if file_path.exists():
            print(f"  [OK] {file_name}")
        else:
            print(f"  [ERR] {file_name} NO existe")
            all_ok = False
    
    return all_ok

def check_config():
    """Verifica archivo de configuración."""
    print("\n📌 Verificando configuración...")
    
    config_file = Path("config.env")
    if not config_file.exists():
        print("  [ERR] config.env NO existe")
        print("     Copiar de: config.example.env")
        return False
    
    print("  [OK] config.env existe")
    
    # Leer configuración
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar variables importantes
    if "OUTPUT_DIR" in content:
        print("  [OK] OUTPUT_DIR configurado")
    
    if "HEADLESS" in content:
        print("  [OK] HEADLESS configurado")
    
    if "USE_OCR" in content:
        print("  [OK] USE_OCR configurado")
    
    return True

def main():
    """Función principal de verificación."""
    print("="*70)
    print("  🔍 VERIFICACIÓN COMPLETA DEL SISTEMA")
    print("  Sistema de Automatización de Trámites GOB.MX v2.0")
    print("  Con Entrada Multimodal (Texto, Voz, Imagen)")
    print("="*70)
    
    results = []
    
    # Verificaciones
    results.append(("Python 3.10+", check_python_version()))
    
    print("\n📌 Verificando dependencias básicas...")
    results.append(("requests", check_module("requests")))
    results.append(("dotenv", check_module("dotenv", "python-dotenv")))
    results.append(("PIL", check_module("PIL", "pillow")))
    results.append(("cryptography", check_module("cryptography")))
    results.append(("colorama", check_module("colorama")))
    
    results.append(("Playwright", check_playwright()))
    results.append(("Tesseract OCR", check_tesseract()))
    results.append(("pytesseract", check_module("pytesseract")))
    results.append(("Whisper", check_whisper()))
    results.append(("Audio libs", check_audio_libs()))
    results.append(("Estructura", check_project_structure()))
    results.append(("Configuración", check_config()))
    
    # Resumen
    print("\n" + "="*70)
    print("  📊 RESUMEN DE VERIFICACIÓN")
    print("="*70)
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = "[OK]" if ok else "[ERR]"
        print(f"  {status} {name}")
    
    print("\n" + "="*70)
    print(f"  Resultado: {passed}/{total} verificaciones pasadas")
    print("="*70)
    
    if passed == total:
        print("\n  🎉 ¡Sistema completamente instalado y listo para usar!")
        print("\n  Ejecuta:")
        print("    python main_multimodal.py")
        print("\n  O con voz:")
        print("    python main_multimodal.py --tramite curp --voice")
        return 0
    else:
        print("\n  [!]️  Hay componentes faltantes. Revisa los errores arriba.")
        print("\n  Instalación rápida:")
        print("    pip install -r requirements.txt")
        print("    python -m playwright install chromium")
        return 1

if __name__ == "__main__":
    sys.exit(main())
