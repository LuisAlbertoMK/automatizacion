#!/usr/bin/env python3
"""
Script de verificación del sistema de automatización
Verifica que todas las dependencias estén instaladas correctamente
"""
import sys
import subprocess

def check_module(module_name, package_name=None):
    """Verifica si un módulo de Python está instalado"""
    if package_name is None:
        package_name = module_name
    
    try:
        __import__(module_name)
        print(f"✅ {package_name} - Instalado")
        return True
    except ImportError:
        print(f"❌ {package_name} - NO instalado")
        return False

def main():
    print("=" * 60)
    print("VERIFICACIÓN DEL SISTEMA DE AUTOMATIZACIÓN")
    print("=" * 60)
    
    print("\n📦 Verificando dependencias de Python...\n")
    
    modules = [
        ("playwright", "playwright"),
        ("requests", "requests"),
        ("dotenv", "python-dotenv"),
        ("PIL", "pillow"),
        ("pytesseract", "pytesseract"),
        ("cryptography", "cryptography"),
        ("imapclient", "imapclient"),
        ("bs4", "beautifulsoup4"),
        ("colorama", "colorama"),
    ]
    
    all_ok = True
    missing = []
    
    for module, package in modules:
        if not check_module(module, package):
            all_ok = False
            missing.append(package)
    
    print("\n" + "=" * 60)
    
    if all_ok:
        print("✅ Todas las dependencias están instaladas")
    else:
        print("❌ Faltan dependencias. Instálalas con:")
        print(f"\n   pip install {' '.join(missing)}")
    
    print("\n🌐 Verificando navegadores de Playwright...\n")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if "chromium" in result.stdout.lower() or result.returncode == 0:
            print("✅ Playwright configurado")
            print("\nPara instalar navegadores ejecuta:")
            print("   python -m playwright install chromium")
        else:
            print("⚠️  Verifica Playwright manualmente")
    except Exception as e:
        print(f"⚠️  No se pudo verificar Playwright: {e}")
        print("\nInstala los navegadores con:")
        print("   python -m playwright install chromium")
    
    print("\n📁 Verificando estructura del proyecto...\n")
    
    import os
    from pathlib import Path
    
    base_dir = Path(__file__).parent
    
    required_files = [
        "main.py",
        "config.env",
        "requirements.txt",
        "utils/__init__.py",
        "utils/captcha.py",
        "utils/storage.py",
        "utils/mail_reader.py",
        "modules/__init__.py",
        "modules/curp.py",
        "modules/nss.py",
    ]
    
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - NO ENCONTRADO")
            all_ok = False
    
    print("\n" + "=" * 60)
    
    if all_ok:
        print("🎉 Sistema listo para usar!")
        print("\nEjecuta: python main.py")
    else:
        print("⚠️  Hay problemas que resolver antes de usar el sistema")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
