#!/usr/bin/env python3
"""
health_check.py — Diagnóstico y health check del Agente de Trámites GOB.MX.
Verifica dependencias, configuración, imports y estado del sistema.

Uso:
    python health_check.py             # Check completo
    python health_check.py --quick     # Solo crítico
    python health_check.py --json      # Salida JSON
"""

import sys
import os
import json
import importlib
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

OK = "\033[92m[OK]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
WARN = "\033[93m[WARN]\033[0m"


def check(module: str, name: str = "", critical: bool = False) -> bool:
    """Verifica que un import funcione."""
    label = name or module
    try:
        importlib.import_module(module)
        print(f"  {OK} {label}")
        return True
    except ImportError as e:
        icon = FAIL if critical else WARN
        print(f"  {icon} {label}: {e}")
        return False
    except Exception as e:
        icon = FAIL if critical else WARN
        print(f"  {icon} {label}: {e}")
        return False


def check_env(key: str, critical: bool = False) -> bool:
    """Verifica variable de entorno."""
    val = os.getenv(key, "")
    if val and val != "tu_api_key_aqui" and "placeholder" not in val.lower() and "your-" not in val.lower():
        print(f"  {OK} {key}")
        return True
    else:
        icon = FAIL if critical else WARN
        print(f"  {icon} {key} {'(no configurada)' if not val else '(placeholder)'}")
        return False


def main():
    load_dotenv = None
    try:
        from dotenv import load_dotenv
        load_dotenv("config.env")
    except Exception:
        pass

    print("=" * 50)
    print("  HEALTH CHECK — Agente de Trámites GOB.MX")
    print("=" * 50)

    # ── Python ──
    print(f"\n[Python]")
    print(f"  Version: {sys.version.split()[0]}")
    print(f"  Path: {sys.executable}")

    # ── Dependencias críticas ──
    print(f"\n[Dependencias]")
    check("playwright", "Playwright", critical=True)
    check("requests", "Requests", critical=True)
    check("dotenv", "python-dotenv", critical=True)
    check("PIL", "Pillow", critical=True)
    check("colorama", "Colorama", critical=True)
    check("cryptography", "Cryptography", critical=True)

    # ── Dependencias opcionales ──
    print(f"\n[Opcionales]")
    check("pytesseract", "Tesseract OCR")
    check("imapclient", "IMAPClient")
    check("whisper", "Whisper (voz)")
    check("sounddevice", "Sounddevice (voz)")
    check("torch", "PyTorch (CNN captcha)")
    check("cv2", "OpenCV (CNN captcha)")
    check("onnxruntime", "ONNX Runtime")

    # ── Módulos del proyecto ──
    print(f"\n[Módulos src/]")
    checks = [
        ("modules.base", "BaseModule"),
        ("modules.curp", "CURPModule"),
        ("modules.nss", "NSSModule"),
        ("modules.antecedentes", "AntecedentesModule"),
        ("modules.tenencia", "TenenciaModule"),
        ("utils.captcha", "CaptchaSolver"),
        ("utils.ocr", "OCRExtractor"),
        ("utils.storage", "Storage"),
        ("utils.logger", "Logger"),
        ("utils.mail_reader", "MailReader"),
    ]
    for mod, name in checks:
        check(mod, name, critical=True)

    # ── Configuración ──
    print(f"\n[Configuración]")
    check_env("CAPTCHA_API_KEY", critical=False)
    check_env("STORAGE_KEY", critical=True)
    check_env("IMAP_EMAIL", critical=False)
    check_env("HEADLESS", critical=False)

    # ── Git ──
    print(f"\n[Git]")
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        print(f"  Branch: {branch}")
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        dirty = len([l for l in status.split("\n") if l.strip()]) if status else 0
        if dirty:
            print(f"  {WARN} {dirty} archivo(s) sin commit")
        else:
            print(f"  {OK} Working tree clean")
    except Exception as e:
        print(f"  {WARN} Git: {e}")

    # ── Verificación final ──
    print(f"\n{'=' * 50}")
    print("  Health check complete")
    print("=" * 50)


if __name__ == "__main__":
    main()
