#!/usr/bin/env python3
"""
auto_diagnostico.py — Diagnóstico automático del Agente de Trámites GOB.MX
Verifica dependencias, configuración, módulos y servicios.
"""

import sys
import os
import subprocess
from pathlib import Path

# ── Helpers ─────────────────────────────────────────────────────────────

def print_header(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def check_ok(msg: str):
    print(f"  [OK] {msg}")
    return True


def check_fail(msg: str):
    print(f"  [ERR] {msg}")
    return False


def check_warn(msg: str):
    print(f"  [!]️  {msg}")
    return True


# ── 1. Python ───────────────────────────────────────────────────────────

def check_python():
    print_header("🐍 Python")
    v = sys.version_info
    if v.major == 3 and v.minor >= 10:
        return check_ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        return check_fail(f"Se requiere Python 3.10+, tienes {v.major}.{v.minor}")


# ── 2. Dependencias ────────────────────────────────────────────────────

def check_dependencies():
    print_header("📦 Dependencias")
    
    # Mapa: nombre pip -> nombre import
    deps = {
        "playwright": "playwright",
        "requests": "requests",
        "python-dotenv": "dotenv",
        "pillow": "PIL",
        "pytesseract": "pytesseract",
        "cryptography": "cryptography",
        "imapclient": "imapclient",
        "beautifulsoup4": "bs4",
        "colorama": "colorama",
    }
    
    all_ok = True
    for pip_name, import_name in deps.items():
        try:
            __import__(import_name)
            check_ok(f"{pip_name}")
        except ImportError:
            check_fail(f"{pip_name} no instalado -> pip install {pip_name}")
            all_ok = False
    
    # Opcionales
    optional = {
        "openai-whisper": "whisper",
        "sounddevice": "sounddevice",
        "numpy": "numpy",
    }
    for pip_name, import_name in optional.items():
        try:
            __import__(import_name)
            check_ok(f"{pip_name} (opcional)")
        except ImportError:
            check_warn(f"{pip_name} no instalado (opcional, para entrada por voz)")
    
    return all_ok


# ── 3. Playwright ──────────────────────────────────────────────────────

def check_playwright():
    print_header("🎭 Playwright")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return check_ok("Chromium disponible y funcional")
    except Exception as e:
        check_fail(f"Playwright/Chromium no disponible: {e}")
        print("    -> Ejecuta: playwright install chromium")
        return False


# ── 4. Configuración ──────────────────────────────────────────────────

def check_config():
    print_header("[GEAR]️  Configuración")
    
    config_file = Path("config.env")
    if not config_file.exists():
        check_fail("config.env no encontrado")
        print("    -> Ejecuta: cp config.example.env config.env")
        return False
    
    check_ok("config.env encontrado")
    
    from dotenv import load_dotenv
    load_dotenv("config.env")
    
    # Verificar claves
    api_key = os.getenv("CAPTCHA_API_KEY", "")
    if api_key and api_key != "tu_api_key_aqui":
        check_ok(f"CAPTCHA_API_KEY configurada ({api_key[:8]}...)")
    else:
        check_warn("CAPTCHA_API_KEY no configurada (CAPTCHAs serán manuales)")
    
    imap = os.getenv("IMAP_EMAIL", "")
    if imap and "@" in imap:
        check_ok(f"IMAP_EMAIL configurado ({imap})")
    else:
        check_warn("IMAP_EMAIL no configurado (NSS vía correo no disponible)")
    
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir.mkdir(exist_ok=True)
    check_ok(f"OUTPUT_DIR: {output_dir}")
    
    return True


# ── 5. Módulos ─────────────────────────────────────────────────────────

def check_modules():
    print_header("🔧 Módulos")
    
    all_ok = True
    modules = [
        ("modules.curp", "CURPModule"),
        ("modules.nss", "NSSModule"),
        ("modules.antecedentes", "AntecedentesModule"),
        ("modules.tenencia", "TenenciaModule"),
        ("modules.orchestrator", "TramitesOrchestrator"),
    ]
    
    for mod_path, class_name in modules:
        try:
            mod = __import__(mod_path, fromlist=[class_name])
            cls = getattr(mod, class_name)
            check_ok(f"{class_name} ({mod_path})")
        except Exception as e:
            check_fail(f"{class_name}: {e}")
            all_ok = False
    
    # Utils
    utils = [
        ("utils.captcha", "CaptchaSolver"),
        ("utils.storage", "save_profile"),
        ("utils.logger", "get_logger"),
    ]
    
    for mod_path, name in utils:
        try:
            mod = __import__(mod_path, fromlist=[name])
            getattr(mod, name)
            check_ok(f"{name} ({mod_path})")
        except Exception as e:
            check_fail(f"{name}: {e}")
            all_ok = False
    
    # Opcionales
    optional_utils = [
        ("utils.ocr", "OCRExtractor"),
        ("utils.voice_input", "VoiceInput"),
        ("utils.multimodal_input", "MultimodalInput"),
        ("utils.mail_reader", "MailReader"),
    ]
    
    for mod_path, name in optional_utils:
        try:
            mod = __import__(mod_path, fromlist=[name])
            getattr(mod, name)
            check_ok(f"{name} ({mod_path}) [opcional]")
        except Exception as e:
            check_warn(f"{name} no disponible: {e}")
    
    return all_ok


# ── 6. Métricas ────────────────────────────────────────────────────────

def check_metrics():
    print_header("📊 Métricas")
    try:
        from utils.logger import TramiteMetrics
        resumen = TramiteMetrics.resumen()
        total = resumen.get("total", 0)
        if total > 0:
            check_ok(f"Total trámites: {total}")
            check_ok(f"Tasa éxito: {resumen.get('tasa_exito', '?')}")
            check_ok(f"Tiempo promedio: {resumen.get('tiempo_promedio_s', '?')}s")
        else:
            check_ok("Sistema de métricas funcional (sin datos aún)")
        return True
    except Exception as e:
        check_warn(f"Métricas no disponibles: {e}")
        return True


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 50)
    print("  🤖 Auto-diagnóstico: Agente Trámites GOB.MX")
    print("=" * 50)
    
    results = {
        "Python": check_python(),
        "Dependencias": check_dependencies(),
        "Configuración": check_config(),
        "Módulos": check_modules(),
        "Métricas": check_metrics(),
    }
    
    # Playwright es lento, preguntar
    print("\n  ¿Verificar Playwright/Chromium? (puede tardar 10s)")
    try:
        resp = input("  [s/N]: ").strip().lower()
        if resp == "s":
            results["Playwright"] = check_playwright()
    except (EOFError, KeyboardInterrupt):
        pass
    
    # Resumen
    print_header("📋 RESUMEN")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, ok in results.items():
        status = "[OK]" if ok else "[ERR]"
        print(f"  {status} {name}")
    
    print(f"\n  Resultado: {passed}/{total} checks pasaron")
    
    if passed == total:
        print("  🎉 SISTEMA LISTO PARA USAR")
    else:
        print("  [!]️  Revisa los errores arriba")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
