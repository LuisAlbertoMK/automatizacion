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

from modules.acta_nacimiento import ActaNacimientoModule
from modules.antecedentes import AntecedentesModule
from modules.buro import BuroModule
from modules.circulo import CirculoModule
from modules.cita_ine import CitaINEModule
from modules.cita_sat import CitaSATModule
from modules.control_confianza import ControlConfianzaModule
from modules.curp import CURPModule
from modules.nss import NSSModule
from modules.pasaporte import PasaporteModule
from modules.rfc import RFCModule
from modules.semanas import SemanasModule
from modules.tenencia import TenenciaModule

try:
    from modules.documentos import CVGenerator, EscritoGenerator
    DOCUMENTOS_AVAILABLE = True
except ImportError:
    DOCUMENTOS_AVAILABLE = False

try:
    from utils.multimodal_input import MultimodalInput
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False


TramiteType = Literal[
    "curp", "nss", "antecedentes", "tenencia", "ambos",
    "rfc", "acta_nacimiento", "pasaporte", "semanas",
    "control_confianza", "buro", "circulo", "cita_ine", "cita_sat",
]
InputMode = Literal["text", "voice", "image", "auto"]


TRAMITES_REGISTRADOS = {
    "curp":              {"modulo": "CURPModule",             "estado": "✅ Producción",     "tiempo": "~16s"},
    "nss":               {"modulo": "NSSModule",              "estado": "✅ Producción",     "tiempo": "~30-60s"},
    "antecedentes":      {"modulo": "AntecedentesModule",     "estado": "🔶 Escrito",        "tiempo": "~45-90s"},
    "tenencia":          {"modulo": "TenenciaModule",         "estado": "🔶 Escrito",        "tiempo": "~20-40s"},
    # ── Migrados de tramites-auto (2026-06-25) ──
    "rfc":               {"modulo": "RFCModule",              "estado": "⚙️ Migrado",       "tiempo": "~30s"},
    "acta_nacimiento":   {"modulo": "ActaNacimientoModule",   "estado": "⚙️ Migrado",       "tiempo": "~30-60s"},
    "pasaporte":         {"modulo": "PasaporteModule",        "estado": "⚙️ Migrado",       "tiempo": "~2-5min"},
    "semanas":           {"modulo": "SemanasModule",          "estado": "⚙️ Migrado",       "tiempo": "~30s"},
    "control_confianza": {"modulo": "ControlConfianzaModule", "estado": "⚙️ Migrado",       "tiempo": "~10-30min"},
    "buro":              {"modulo": "BuroModule",             "estado": "⚙️ Migrado",       "tiempo": "~5-10min"},
    "circulo":           {"modulo": "CirculoModule",          "estado": "⚙️ Migrado",       "tiempo": "~5-10min"},
    "cita_ine":          {"modulo": "CitaINEModule",          "estado": "⚙️ Migrado",       "tiempo": "~5min"},
    "cita_sat":          {"modulo": "CitaSATModule",          "estado": "⚙️ Migrado",       "tiempo": "~5min"},
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

        # ── Módulos migrados de tramites-auto ──
        self.rfc_module = RFCModule(captcha_solver=captcha_solver, use_ocr=True)
        self.acta_nacimiento_module = ActaNacimientoModule(captcha_solver=captcha_solver, use_ocr=True)
        self.pasaporte_module = PasaporteModule(captcha_solver=captcha_solver, use_ocr=True)
        self.semanas_module = SemanasModule(captcha_solver=captcha_solver, use_ocr=True)
        self.control_confianza_module = ControlConfianzaModule(captcha_solver=captcha_solver, use_ocr=True)
        self.buro_module = BuroModule(captcha_solver=captcha_solver, use_ocr=True)
        self.circulo_module = CirculoModule(captcha_solver=captcha_solver, use_ocr=True)
        self.cita_ine_module = CitaINEModule(captcha_solver=captcha_solver, use_ocr=True)
        self.cita_sat_module = CitaSATModule(captcha_solver=captcha_solver, use_ocr=True)

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

        elif tipo == "rfc":
            return await self._ejecutar_rfc(modo_entrada)
        elif tipo == "acta_nacimiento":
            return await self._ejecutar_acta(modo_entrada)
        elif tipo == "pasaporte":
            return await self._ejecutar_pasaporte(modo_entrada)
        elif tipo == "semanas":
            return await self._ejecutar_semanas(modo_entrada)
        elif tipo == "control_confianza":
            return await self._ejecutar_control_confianza(modo_entrada)
        elif tipo == "buro":
            return await self._ejecutar_buro(modo_entrada)
        elif tipo == "circulo":
            return await self._ejecutar_circulo(modo_entrada)
        elif tipo == "cita_ine":
            return await self._ejecutar_cita_ine(modo_entrada)
        elif tipo == "cita_sat":
            return await self._ejecutar_cita_sat(modo_entrada)

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
        from utils.pii import sanitize_curp, sanitize_nss
        print(f"\n{'='*60}")
        print("  RESUMEN FINAL")
        print(f"{'='*60}")
        print(f"  CURP:  {sanitize_curp(res_curp.get('curp', '—'))}")
        print(f"  NSS:   {sanitize_nss(res_nss.get('nss', '—'))}")
        if res_curp.get("pdf_path"):
            print(f"  PDF CURP: {res_curp['pdf_path']}")
        print(f"{'='*60}\n")

        return resultados

    async def _ejecutar_rfc(self, modo: InputMode) -> dict:
        """Ejecuta consulta de RFC."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
        else:
            curp = input("  CURP (18 caracteres): ").strip().upper()
        nombre = input("  Nombre (opcional): ").strip() or ""
        ap_pat = input("  Apellido paterno (opcional): ").strip() or ""
        ap_mat = input("  Apellido materno (opcional): ").strip() or ""
        return await self.rfc_module.consultar(
            curp=curp, nombre=nombre, apellido_paterno=ap_pat, apellido_materno=ap_mat
        )

    async def _ejecutar_acta(self, modo: InputMode) -> dict:
        """Ejecuta descarga de Acta de Nacimiento."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
        else:
            curp = input("  CURP (18 caracteres): ").strip().upper()
        return await self.acta_nacimiento_module.consultar(curp=curp)

    async def _ejecutar_pasaporte(self, modo: InputMode) -> dict:
        """Ejecuta cita de pasaporte."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
        else:
            curp = input("  CURP (18 caracteres): ").strip().upper()
        nombre = input("  Nombre (opcional): ").strip() or ""
        ap_pat = input("  Apellido paterno (opcional): ").strip() or ""
        ap_mat = input("  Apellido materno (opcional): ").strip() or ""
        estado = input("  Estado/delegación (default MEX): ").strip() or "MEX"
        tel = input("  Teléfono (opcional): ").strip() or ""
        email = input("  Email (opcional): ").strip() or ""
        return await self.pasaporte_module.consultar(
            curp=curp, nombre=nombre, apellido_paterno=ap_pat,
            apellido_materno=ap_mat, estado=estado, telefono=tel, email=email
        )

    async def _ejecutar_semanas(self, modo: InputMode) -> dict:
        """Ejecuta consulta de semanas cotizadas."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
        else:
            curp = input("  CURP (18 caracteres): ").strip().upper()
        nss = input("  NSS (si lo tenés, opcional): ").strip() or ""
        return await self.semanas_module.consultar(curp=curp, nss=nss)

    async def _ejecutar_control_confianza(self, modo: InputMode) -> dict:
        """Ejecuta Control de Confianza."""
        curp = input("  CURP (18 caracteres): ").strip().upper()
        rfc = input("  RFC (opcional): ").strip() or ""
        nombre = input("  Nombre completo: ").strip() or ""
        fecha_nac = input("  Fecha de nacimiento (DD/MM/YYYY): ").strip() or ""
        edo_nac = input("  Estado de nacimiento: ").strip() or ""
        return await self.control_confianza_module.consultar(
            curp=curp, rfc=rfc, nombre=nombre,
            fecha_nacimiento=fecha_nac, estado_nacimiento=edo_nac
        )

    async def _ejecutar_buro(self, modo: InputMode) -> dict:
        """Ejecuta consulta de Buró de Crédito."""
        rfc = input("  RFC: ").strip().upper()
        curp = input("  CURP: ").strip().upper()
        nombre = input("  Nombre (opcional): ").strip() or ""
        ap_pat = input("  Apellido paterno (opcional): ").strip() or ""
        ap_mat = input("  Apellido materno (opcional): ").strip() or ""
        fecha = input("  Fecha de nacimiento (DD/MM/YYYY, opcional): ").strip() or ""
        return await self.buro_module.consultar(
            rfc=rfc, curp=curp, nombre=nombre,
            apellido_paterno=ap_pat, apellido_materno=ap_mat,
            fecha_nacimiento=fecha
        )

    async def _ejecutar_circulo(self, modo: InputMode) -> dict:
        """Ejecuta consulta de Círculo de Crédito."""
        rfc = input("  RFC: ").strip().upper()
        curp = input("  CURP: ").strip().upper()
        nombre = input("  Nombre (opcional): ").strip() or ""
        ap_pat = input("  Apellido paterno (opcional): ").strip() or ""
        ap_mat = input("  Apellido materno (opcional): ").strip() or ""
        fecha = input("  Fecha de nacimiento (DD/MM/YYYY, opcional): ").strip() or ""
        return await self.circulo_module.consultar(
            rfc=rfc, curp=curp, nombre=nombre,
            apellido_paterno=ap_pat, apellido_materno=ap_mat,
            fecha_nacimiento=fecha
        )

    async def _ejecutar_cita_ine(self, modo: InputMode) -> dict:
        """Ejecuta cita INE."""
        if self.multimodal:
            curp = self.multimodal.get_curp(mode=modo)
        else:
            curp = input("  CURP (18 caracteres): ").strip().upper()
        nombre = input("  Nombre (opcional): ").strip() or ""
        return await self.cita_ine_module.consultar(curp=curp, nombre=nombre)

    async def _ejecutar_cita_sat(self, modo: InputMode) -> dict:
        """Ejecuta cita SAT."""
        rfc = input("  RFC: ").strip().upper()
        curp = input("  CURP (opcional): ").strip().upper() or ""
        email = input("  Email (opcional): ").strip() or ""
        return await self.cita_sat_module.consultar(rfc=rfc, curp=curp, email=email)

    # ── Documentos ───────────────────────────────────────────────────────────

    async def generar_cv_interactivo(self) -> dict:
        """Genera CV profesional interactivo."""
        if not DOCUMENTOS_AVAILABLE:
            print("  Módulo de documentos no disponible. Instalá: pip install python-docx")
            return {"status": "error", "error": "python-docx no instalado"}
        gen = CVGenerator()
        return gen.generar_interactivo()

    async def generar_escrito_interactivo(self) -> dict:
        """Genera escrito/carta interactivo."""
        if not DOCUMENTOS_AVAILABLE:
            print("  Módulo de documentos no disponible. Instalá: pip install python-docx")
            return {"status": "error", "error": "python-docx no instalado"}
        gen = EscritoGenerator()
        return gen.generar_interactivo()

    async def modo_interactivo(self):
        """Modo interactivo con menú de opciones (async)."""
        print("\n" + "="*60)
        print("  SISTEMA DE TRÁMITES GUBERNAMENTALES")
        print("  Entrada Multimodal: Texto, Voz, Imagen")
        print("="*60)

        while True:
            print("\n  Trámites disponibles:")
            print("  1)  CURP - Consulta y descarga")
            print("  2)  NSS - Número de Seguridad Social")
            print("  3)  Antecedentes No Penales")
            print("  4)  Tenencia Vehicular")
            print("  5)  CURP + NSS (ambos)")
            print("  ── Migrados ──")
            print("  6)  RFC SAT")
            print("  7)  Acta de Nacimiento (RENAPO)")
            print("  8)  Cita Pasaporte SRE")
            print("  9)  Semanas Cotizadas IMSS")
            print("  10) Control de Confianza (SESNSP)")
            print("  11) Buró de Crédito")
            print("  12) Círculo de Crédito")
            print("  13) Cita INE")
            print("  14) Cita SAT")
            print("  ── Documentos ──")
            print("  15) CV - Generar CV profesional con IA")
            print("  16) Escrito - Carta / Contrato / Documento legal con IA")
            print("  ──")
            print("  0)  Salir")

            opcion = input("\n  Selecciona opción: ").strip()

            if opcion in ("0", "salir", "exit"):
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
                    await self.ejecutar_tramite("curp", modo)
                elif opcion == "2":
                    await self.ejecutar_tramite("nss", modo)
                elif opcion == "3":
                    await self.ejecutar_tramite("antecedentes", modo)
                elif opcion == "4":
                    await self.ejecutar_tramite("tenencia", modo)
                elif opcion == "5":
                    await self.ejecutar_tramite("ambos", modo)
                elif opcion == "6":
                    await self.ejecutar_tramite("rfc", modo)
                elif opcion == "7":
                    await self.ejecutar_tramite("acta_nacimiento", modo)
                elif opcion == "8":
                    await self.ejecutar_tramite("pasaporte", modo)
                elif opcion == "9":
                    await self.ejecutar_tramite("semanas", modo)
                elif opcion == "10":
                    await self.ejecutar_tramite("control_confianza", modo)
                elif opcion == "11":
                    await self.ejecutar_tramite("buro", modo)
                elif opcion == "12":
                    await self.ejecutar_tramite("circulo", modo)
                elif opcion == "13":
                    await self.ejecutar_tramite("cita_ine", modo)
                elif opcion == "14":
                    await self.ejecutar_tramite("cita_sat", modo)
                elif opcion == "15":
                    await self.generar_cv_interactivo()
                elif opcion == "16":
                    await self.generar_escrito_interactivo()
                else:
                    print("  Opción inválida")

            except KeyboardInterrupt:
                print("\n  Trámite cancelado")
            except Exception as e:
                print(f"  Error: {e}")

    def modo_interactivo_sync(self):
        """Wrapper sincrónico para modo_interactivo (usa asyncio.run internamente)."""
        asyncio.run(self.modo_interactivo())
