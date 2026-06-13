"""
modules/orchestrator.py
Orquestador de trámites con entrada multimodal

Funcionalidades:
  - Ejecuta trámites con entrada por texto, voz o imagen
  - Gestiona flujos completos de múltiples trámites
  - Interfaz unificada para todos los módulos
"""

import asyncio
from typing import Literal

from modules.antecedentes import AntecedentesModule
from modules.curp import CURPModule
from modules.nss import NSSModule
from modules.tenencia import TenenciaModule

try:
    from utils.multimodal_input import MultimodalInput
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False


TramiteType = Literal["curp", "nss", "antecedentes", "tenencia", "ambos"]
InputMode = Literal["text", "voice", "image", "auto"]


TRAMITES_REGISTRADOS = {
    "curp":          {"modulo": "CURPModule",       "estado": "✅ Producción", "tiempo": "~16s"},
    "nss":           {"modulo": "NSSModule",        "estado": "✅ Producción", "tiempo": "~30-60s"},
    "antecedentes":  {"modulo": "AntecedentesModule", "estado": "🔶 Escrito", "tiempo": "~45-90s"},
    "tenencia":      {"modulo": "TenenciaModule",   "estado": "🔶 Escrito",   "tiempo": "~20-40s"},
    # ── Próximos ──
    "rfc":           {"modulo": None, "estado": "📋 Planificado", "tiempo": "—"},
    "semanas_imss":  {"modulo": None, "estado": "📋 Planificado", "tiempo": "—"},
    "pasaporte":     {"modulo": None, "estado": "📋 Planificado", "tiempo": "—"},
    "ine":           {"modulo": None, "estado": "📋 Planificado", "tiempo": "—"},
    "licencia":      {"modulo": None, "estado": "📋 Planificado", "tiempo": "—"},
}


def listar_tramites() -> dict:
    """Retorna todos los trámites con su estado."""
    return dict(TRAMITES_REGISTRADOS)


class TramitesOrchestrator:
    """Orquestador de trámites gubernamentales con entrada multimodal."""

    def __init__(self, captcha_solver=None, mail_reader=None, voice_model="base"):
        """
        Inicializa el orquestador.
        
        Args:
            captcha_solver: Solver de CAPTCHAs (opcional)
            mail_reader: Lector de correos (opcional)
            voice_model: Modelo de Whisper para voz
        """
        # Módulos de trámites
        self.curp_module = CURPModule(captcha_solver=captcha_solver, use_ocr=True)
        self.nss_module = NSSModule(
            captcha_solver=captcha_solver,
            mail_reader=mail_reader,
            use_ocr=True
        )
        self.antecedentes_module = AntecedentesModule(
            captcha_solver=captcha_solver,
            use_ocr=True
        )
        self.tenencia_module = TenenciaModule(
            captcha_solver=captcha_solver,
            use_ocr=True
        )

        # Entrada multimodal
        if MULTIMODAL_AVAILABLE:
            self.multimodal = MultimodalInput(voice_model=voice_model)
        else:
            self.multimodal = None
            print("  [ORCHESTRATOR] [!] Entrada multimodal no disponible")

    async def ejecutar_tramite(self, tipo: TramiteType, modo_entrada: InputMode = "text") -> dict:
        """
        Ejecuta un trámite con el modo de entrada especificado.
        
        Args:
            tipo: Tipo de trámite a ejecutar
            modo_entrada: "text", "voice", "image", "auto"
        
        Returns:
            Resultado del trámite
        """
        print(f"\n{'='*60}")
        print(f"  TRÁMITE: {tipo.upper()}")
        print(f"  Modo de entrada: {modo_entrada}")
        print(f"{'='*60}\n")

        if tipo == "curp":
            return await self._ejecutar_curp(modo_entrada)

        elif tipo == "nss":
            return await self._ejecutar_nss(modo_entrada)

        elif tipo == "antecedentes":
            return await self._ejecutar_antecedentes(modo_entrada)

        elif tipo == "tenencia":
            return await self._ejecutar_tenencia(modo_entrada)

        elif tipo == "ambos":
            return await self._ejecutar_ambos(modo_entrada)

        else:
            raise ValueError(f"Tipo de trámite no soportado: {tipo}")

    async def _ejecutar_curp(self, modo: InputMode) -> dict:
        """Ejecuta trámite de CURP."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
        else:
            curp = input("  CURP (18 caracteres): ").strip().upper()

        return await self.curp_module.consultar(curp=curp)

    async def _ejecutar_nss(self, modo: InputMode) -> dict:
        """Ejecuta trámite de NSS."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
            correo = self.multimodal.get_email(mode=modo)
        else:
            curp = input("  CURP: ").strip().upper()
            correo = input("  Correo electrónico: ").strip()

        return await self.nss_module.consultar(curp=curp, correo=correo)

    async def _ejecutar_antecedentes(self, modo: InputMode) -> dict:
        """Ejecuta trámite de Antecedentes No Penales."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
            correo = self.multimodal.get_email(mode=modo)
        else:
            curp = input("  CURP: ").strip().upper()
            correo = input("  Correo electrónico: ").strip()

        # Preguntar si tiene cuenta
        tiene_cuenta = input("  ¿Ya tienes cuenta en el portal? (s/n): ").strip().lower()
        password = None

        if tiene_cuenta == "s":
            password = input("  Contraseña: ").strip()

        return await self.antecedentes_module.consultar(
            curp=curp,
            correo=correo,
            password=password
        )

    async def _ejecutar_tenencia(self, modo: InputMode) -> dict:
        """Ejecuta consulta de Tenencia."""
        if self.multimodal:
            placa = self.multimodal.get_placa(mode=modo)
        else:
            placa = input("  Placa vehicular: ").strip().upper()

        # Número de serie opcional
        tiene_serie = input("  ¿Tienes el número de serie/VIN? (s/n): ").strip().lower()
        numero_serie = None

        if tiene_serie == "s":
            numero_serie = input("  Número de serie: ").strip()

        return await self.tenencia_module.consultar(
            placa=placa,
            numero_serie=numero_serie
        )

    async def _ejecutar_ambos(self, modo: InputMode) -> dict:
        """Ejecuta CURP y NSS en secuencia."""
        print("\n  Ejecutando CURP + NSS...")

        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
            correo = self.multimodal.get_email(mode=modo)
        else:
            curp = input("  CURP: ").strip().upper()
            correo = input("  Correo electrónico: ").strip()

        resultados = {}

        # CURP
        print("\n  [1/2] Ejecutando CURP...")
        res_curp = await self.curp_module.consultar(curp=curp)
        resultados["curp"] = res_curp

        # NSS
        print("\n  [2/2] Ejecutando NSS...")
        res_nss = await self.nss_module.consultar(curp=curp, correo=correo)
        resultados["nss"] = res_nss

        # Resumen
        print(f"\n{'='*60}")
        print("  RESUMEN FINAL")
        print(f"{'='*60}")
        print(f"  CURP:  {res_curp.get('curp', '—')}")
        print(f"  NSS:   {res_nss.get('nss', '—')}")
        if res_curp.get("pdf_path"):
            print(f"  PDF CURP: {res_curp['pdf_path']}")
        print(f"{'='*60}\n")

        return resultados

    def modo_interactivo(self):
        """Modo interactivo con menú de opciones."""
        print("\n" + "="*60)
        print("  🤖 SISTEMA DE TRÁMITES GUBERNAMENTALES")
        print("  Entrada Multimodal: Texto, Voz, Imagen")
        print("="*60)

        while True:
            print("\n  Trámites disponibles:")
            print("  1) CURP - Consulta y descarga")
            print("  2) NSS - Número de Seguridad Social")
            print("  3) Antecedentes No Penales")
            print("  4) Tenencia Vehicular")
            print("  5) CURP + NSS (ambos)")
            print("  6) Salir")

            opcion = input("\n  Selecciona opción: ").strip()

            if opcion == "6":
                print("  Hasta luego.")
                break

            # Seleccionar modo de entrada
            if self.multimodal:
                print("\n  Modo de entrada:")
                print("  1) Texto (teclado)")
                if self.multimodal.voice:
                    print("  2) Voz (micrófono)")
                if self.multimodal.ocr:
                    print("  3) Imagen (foto/archivo)")

                modo_opcion = input("  Modo: ").strip()

                if modo_opcion == "2" and self.multimodal.voice:
                    modo = "voice"
                elif modo_opcion == "3" and self.multimodal.ocr:
                    modo = "image"
                else:
                    modo = "text"
            else:
                modo = "text"

            # Ejecutar trámite
            try:
                if opcion == "1":
                    asyncio.run(self.ejecutar_tramite("curp", modo))
                elif opcion == "2":
                    asyncio.run(self.ejecutar_tramite("nss", modo))
                elif opcion == "3":
                    asyncio.run(self.ejecutar_tramite("antecedentes", modo))
                elif opcion == "4":
                    asyncio.run(self.ejecutar_tramite("tenencia", modo))
                elif opcion == "5":
                    asyncio.run(self.ejecutar_tramite("ambos", modo))
                else:
                    print("  Opción inválida")

            except KeyboardInterrupt:
                print("\n  Trámite cancelado")
            except Exception as e:
                print(f"  Error: {e}")
