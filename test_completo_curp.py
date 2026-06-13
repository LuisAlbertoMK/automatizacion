#!/usr/bin/env python3
"""
Test completo del módulo CURP con la CURP de prueba: OOLL940914HMCRGS08
Verifica que todo el sistema esté funcionando correctamente.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Cargar configuración
load_dotenv("config.env")

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from modules.curp import CURPModule
from utils.captcha import CaptchaSolver, CaptchaError


def verificar_requisitos():
    """Verifica que todos los requisitos estén instalados."""
    print("=" * 60)
    print("🔍 VERIFICANDO REQUISITOS DEL SISTEMA")
    print("=" * 60)
    
    requisitos = {
        "playwright": "Navegador automatizado",
        "requests": "Cliente HTTP",
        "dotenv": "Variables de entorno",
        "colorama": "Colores en terminal",
        "PIL": "Procesamiento de imágenes",
    }
    
    faltantes = []
    
    for modulo, descripcion in requisitos.items():
        try:
            __import__(modulo)
            print(f"[OK] {modulo:15} - {descripcion}")
        except ImportError:
            print(f"[ERR] {modulo:15} - {descripcion} (FALTANTE)")
            faltantes.append(modulo)
    
    if faltantes:
        print(f"\n[!]️  Faltan {len(faltantes)} dependencias:")
        print(f"   pip install {' '.join(faltantes)}")
        return False
    
    print("\n[OK] Todos los requisitos están instalados")
    return True


def verificar_configuracion():
    """Verifica que la configuración esté correcta."""
    print("\n" + "=" * 60)
    print("🔍 VERIFICANDO CONFIGURACIÓN")
    print("=" * 60)
    
    # Verificar archivo config.env
    if not Path("config.env").exists():
        print("[ERR] Archivo config.env no encontrado")
        print("   Copia config.example.env a config.env")
        return False
    
    print("[OK] Archivo config.env encontrado")
    
    # Verificar API key de 2captcha
    api_key = os.getenv("CAPTCHA_API_KEY", "")
    if not api_key or api_key == "tu_api_key_aqui":
        print("[!]️  API key de 2captcha no configurada")
        print("   El CAPTCHA será manual")
        return True  # No es crítico
    
    print(f"[OK] API key de 2captcha configurada: {api_key[:10]}...")
    
    # Verificar directorios
    dirs = ["output", "data", "modules", "utils"]
    for d in dirs:
        if Path(d).exists():
            print(f"[OK] Directorio {d}/ existe")
        else:
            print(f"[!]️  Directorio {d}/ no existe, creando...")
            Path(d).mkdir(exist_ok=True)
    
    return True


async def test_curp_completo(curp: str = "OOLL940914HMCRGS08"):
    """
    Prueba completa del módulo CURP.
    
    Args:
        curp: CURP de prueba (default: OOLL940914HMCRGS08)
    """
    print("\n" + "=" * 60)
    print(f"🧪 PRUEBA COMPLETA - MÓDULO CURP")
    print("=" * 60)
    print(f"\n📋 CURP de prueba: {curp}")
    
    # Inicializar solver de CAPTCHA
    api_key = os.getenv("CAPTCHA_API_KEY", "")
    solver = None
    
    if api_key and api_key != "tu_api_key_aqui":
        try:
            solver = CaptchaSolver(api_key)
            print("[OK] CaptchaSolver inicializado")
        except CaptchaError as e:
            print(f"[!]️  CaptchaSolver: {e}")
            print("   Continuando sin solver automático")
    else:
        print("[!]️  Sin API key de 2captcha - CAPTCHA será manual")
    
    # Inicializar módulo CURP
    print("\n🔄 Inicializando módulo CURP...")
    try:
        modulo = CURPModule(captcha_solver=solver)
        print("[OK] Módulo CURP inicializado correctamente")
    except Exception as e:
        print(f"[ERR] Error al inicializar módulo CURP: {e}")
        return False
    
    # Ejecutar consulta
    print(f"\n🚀 Consultando CURP: {curp}")
    print("   (Esto puede tardar 30-60 segundos...)")
    
    try:
        resultado = await modulo.consultar(curp=curp)
        
        # Mostrar resultado
        print("\n" + "=" * 60)
        print("[OK] RESULTADO DE LA CONSULTA")
        print("=" * 60)
        
        if resultado.get("success"):
            print("[OK] Consulta exitosa")
            
            for clave, valor in resultado.items():
                if clave != "success" and valor:
                    print(f"   {clave.upper():15}: {valor}")
            
            # Verificar PDF
            if resultado.get("pdf_path"):
                pdf_path = Path(resultado["pdf_path"])
                if pdf_path.exists():
                    size_kb = pdf_path.stat().st_size / 1024
                    print(f"\n📄 PDF descargado:")
                    print(f"   Ruta: {pdf_path}")
                    print(f"   Tamaño: {size_kb:.1f} KB")
                else:
                    print(f"\n[!]️  PDF reportado pero no encontrado: {pdf_path}")
        else:
            print("[ERR] Consulta falló")
            if resultado.get("error"):
                print(f"   Error: {resultado['error']}")
        
        print("=" * 60)
        return resultado.get("success", False)
        
    except KeyboardInterrupt:
        print("\n\n[!]️  Prueba interrumpida por el usuario")
        return False
    except Exception as e:
        print(f"\n[ERR] Error durante la consulta: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Función principal de prueba."""
    print("\n" + "=" * 60)
    print("🤖 TEST COMPLETO - SISTEMA DE AUTOMATIZACIÓN CURP")
    print("=" * 60)
    
    # 1. Verificar requisitos
    if not verificar_requisitos():
        print("\n[ERR] Faltan requisitos. Instala las dependencias y vuelve a intentar.")
        return False
    
    # 2. Verificar configuración
    if not verificar_configuracion():
        print("\n[ERR] Configuración incompleta. Revisa config.env")
        return False
    
    # 3. Ejecutar prueba de CURP
    curp_prueba = "OOLL940914HMCRGS08"
    exito = await test_curp_completo(curp_prueba)
    
    # 4. Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN FINAL")
    print("=" * 60)
    
    if exito:
        print("[OK] TODAS LAS PRUEBAS PASARON")
        print("\n💡 El sistema está funcionando correctamente")
        print("   Puedes ejecutar: python main.py")
    else:
        print("[ERR] ALGUNAS PRUEBAS FALLARON")
        print("\n💡 Revisa los errores anteriores")
        print("   Posibles causas:")
        print("   - Falta configurar API key de 2captcha")
        print("   - Problema de conexión a internet")
        print("   - El sitio de GOB.MX cambió su estructura")
        print("   - Navegador Chromium no instalado (ejecuta: playwright install chromium)")
    
    print("=" * 60)
    return exito


if __name__ == "__main__":
    try:
        resultado = asyncio.run(main())
        sys.exit(0 if resultado else 1)
    except KeyboardInterrupt:
        print("\n\n[STOP]️  Prueba cancelada por el usuario")
        sys.exit(1)
