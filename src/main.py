#!/usr/bin/env python3
"""
main.py
Agente principal — CLI interactivo para automatizar trámites.

Uso:
    python main.py                              # Modo interactivo
    python main.py --tramite curp --curp XXXX   # Directo
    python main.py --tramite nss --curp XXXX --correo a@b.com
    python main.py --perfil juan_garcia         # Con perfil guardado
"""

import argparse
import asyncio
import os
import re
import signal
import sys
from pathlib import Path

from colorama import Fore, Style
from colorama import init as colorama_init
from dotenv import load_dotenv

# ── Agregar src/ al path ──────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

# ── Cargar configuración ──────────────────────────────────────────────────────
load_dotenv("config.env")
colorama_init(autoreset=True)


def _validar_config():
    """Valida config esencial al startup. Warn si faltan cosas críticas."""
    issues = []
    if not os.getenv("STORAGE_KEY"):
        issues.append("STORAGE_KEY no configurada — los perfiles no se guardarán")
    api_key = os.getenv("CAPTCHA_API_KEY", "")
    if not api_key or api_key == "tu_api_key_aqui":
        issues.append("CAPTCHA_API_KEY no configurada — captchas serán manuales")
    if issues:
        print(f"  {Fore.YELLOW}[!] Configuración:{Style.RESET_ALL}")
        for i in issues:
            print(f"    {Fore.YELLOW}⚠  {i}{Style.RESET_ALL}")


def _listar_tramites():
    """Muestra todos los trámites registrados y su estado."""
    from modules.orchestrator import listar_tramites
    tramites = listar_tramites()
    print(f"\n  {Fore.CYAN}Trámites disponibles:{Style.RESET_ALL}")
    for nombre, info in tramites.items():
        print(f"    {nombre:20s} {info['estado']}  {info['tiempo']}")
    print()


# ── Importar módulos del agente ───────────────────────────────────────────────
from modules.acta_nacimiento import ActaNacimientoModule  # noqa: E402
from modules.buro import BuroModule  # noqa: E402
from modules.circulo import CirculoModule  # noqa: E402
from modules.cita_ine import CitaINEModule  # noqa: E402
from modules.cita_sat import CitaSATModule  # noqa: E402
from modules.control_confianza import ControlConfianzaModule  # noqa: E402
from modules.curp import CURPModule  # noqa: E402
from modules.nss import NSSModule  # noqa: E402
from modules.pasaporte import PasaporteModule  # noqa: E402
from modules.rfc import RFCModule  # noqa: E402
from modules.semanas import SemanasModule  # noqa: E402
from utils.captcha import CaptchaError, CaptchaSolver  # noqa: E402
from utils.storage import list_profiles, load_profile, save_profile  # noqa: E402

try:
    from utils.mail_reader import MailReader, MailReaderError  # noqa: F401
    MAIL_AVAILABLE = True
except ImportError:
    MAIL_AVAILABLE = False

try:
    from utils.free_captcha import FreeCaptchaSolver
    FREE_SOLVER_AVAILABLE = True
except ImportError:
    FREE_SOLVER_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
BANNER = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════╗
║  🤖  Agente de Trámites GOB.MX  — v2.0  (jun 2026)          ║
║  Módulos: CURP · NSS · RFC · Acta · Pasaporte · Semanas      ║
║           Antecedentes · Tenencia · ControlConf · Buró        ║
║           Círculo · CitaINE · CitaSAT                         ║
╚════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""

AYUDA = f"""
{Fore.YELLOW}Comandos disponibles:{Style.RESET_ALL}
  curp             -> Consultar y descargar CURP
  nss              -> Obtener NSS del IMSS
  rfc              -> Consultar RFC SAT
  acta             -> Descargar Acta de Nacimiento
  pasaporte        -> Cita de Pasaporte SRE
  semanas          -> Semanas Cotizadas IMSS
  control_confianza -> Control de Confianza SESNSP
  buro             -> Buró de Crédito
  circulo          -> Círculo de Crédito
  cita_ine         -> Cita INE
  cita_sat         -> Cita SAT
  ambos            -> CURP + NSS en una sola operación
  perfil           -> Ver, guardar o cargar un perfil
  ayuda            -> Mostrar esta pantalla
  salir            -> Salir del programa
"""


# ─────────────────────────────────────────────────────────────────────────────
class Agente:
    def __init__(self):
        self.solver      = None
        self.mail_reader = None
        self._init_services()

    def _init_services(self):
        """Inicializa servicios externos (captcha, mail)."""
        api_key = os.getenv("CAPTCHA_API_KEY", "")
        if api_key and api_key != "tu_api_key_aqui":
            try:
                self.solver = CaptchaSolver(api_key)
                print(f"{Fore.GREEN}  [OK] 2captcha conectado{Style.RESET_ALL}")
            except CaptchaError as e:
                print(f"{Fore.YELLOW}  [!] 2captcha: {e}{Style.RESET_ALL}")

        # Fallback al solver gratuito si no hay 2captcha configurado
        if not self.solver and FREE_SOLVER_AVAILABLE:
            try:
                self.solver = FreeCaptchaSolver()
                print(f"{Fore.CYAN}  [OK] FreeCaptchaSolver activo (OCR + Whisper){Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}  [!] FreeCaptchaSolver: {e}{Style.RESET_ALL}")

        if not self.solver:
            print(f"{Fore.YELLOW}  [!] Sin solver de CAPTCHA — serán manuales{Style.RESET_ALL}")

        if MAIL_AVAILABLE:
            imap_email = os.getenv("IMAP_EMAIL", "")
            imap_pass  = os.getenv("IMAP_PASSWORD", "")
            # Placeholder emails conocidos — saltar MailReader
            placeholders = ("tucorreo", "your-email", "placeholder", "@example.com")
            is_placeholder = any(p in imap_email.lower() for p in placeholders)
            if imap_email and "@" in imap_email and not is_placeholder and imap_pass:
                try:
                    self.mail_reader = MailReader()
                    print(f"{Fore.GREEN}  [OK] IMAP configurado ({imap_email}){Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.YELLOW}  [!] IMAP: {e}{Style.RESET_ALL}")

    # ── CURP ──────────────────────────────────────────────────────────────────
    async def tramite_curp(self, perfil: dict = None) -> dict:
        """Ejecuta el trámite de CURP."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: CURP ━━━{Style.RESET_ALL}")

        if perfil and perfil.get("curp"):
            curp = perfil["curp"]
            print(f"  Usando CURP del perfil: {curp[:4]}****")
        else:
            curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)

        modulo = CURPModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(curp=curp)

        self._mostrar_resultado("CURP", resultado)
        return resultado

    # ── NSS ───────────────────────────────────────────────────────────────────
    async def tramite_nss(self, perfil: dict = None) -> dict:
        """Ejecuta el trámite de NSS."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: NSS IMSS ━━━{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}  Usando CNN solver local (85% char accuracy, ~50ms){Style.RESET_ALL}")
        if not self.mail_reader:
            print(f"{Fore.YELLOW}  [!] Sin lector de correo — el NSS se envía por email{Style.RESET_ALL}")

        if perfil and perfil.get("curp"):
            curp = perfil["curp"]
            print(f"  Usando CURP del perfil: {curp[:4]}****")
        else:
            curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)

        correo_default = perfil.get("correo", "") if perfil else ""
        correo_hint    = f" [{correo_default}]" if correo_default else ""
        correo = self._pedir_dato(
            f"Correo electrónico{correo_hint}",
            default=correo_default,
            validar=lambda x: "@" in x and "." in x,
        )

        modulo = NSSModule(captcha_solver=self.solver, mail_reader=self.mail_reader)
        resultado = await modulo.consultar(curp=curp, correo=correo)

        # Si el NSS fue enviado al correo, mostrar instrucciones claras
        if resultado.get("nss") == "ENVIADO_AL_CORREO":
            print(f"\n{Fore.GREEN}{'━'*50}")
            print("  SOLICITUD ENVIADA CON ÉXITO")
            print(f"{'━'*50}{Style.RESET_ALL}")
            print(f"  El IMSS envió el NSS al correo: {correo}")
            print()
            print(f"  {Fore.YELLOW}Para obtenerlo automáticamente la próxima vez:{Style.RESET_ALL}")
            print("  1. Configurá IMAP en config.env:")
            print(f"     IMAP_EMAIL={correo}")
            print("     IMAP_PASSWORD=tu_contraseña_de_aplicación")
            print()
            print(f"  {Fore.CYAN}O revisá manualmente tu bandeja de entrada.{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{'━'*50}{Style.RESET_ALL}\n")
        else:
            self._mostrar_resultado("NSS", resultado)

        return resultado

    # ── AMBOS ─────────────────────────────────────────────────────────────────
    async def tramite_ambos(self, perfil: dict = None) -> dict:
        """Ejecuta CURP y NSS de forma secuencial."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITES: CURP + NSS IMSS ━━━{Style.RESET_ALL}")

        if perfil and perfil.get("curp"):
            curp = perfil["curp"]
        else:
            curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)

        correo_default = perfil.get("correo", "") if perfil else ""
        correo_hint    = f" [{correo_default}]" if correo_default else ""
        correo = self._pedir_dato(
            f"Correo electrónico{correo_hint}",
            default=correo_default,
            validar=lambda x: "@" in x and "." in x,
        )

        resultados = {}

        # CURP
        modulo_curp = CURPModule(captcha_solver=self.solver)
        res_curp    = await modulo_curp.consultar(curp=curp)
        resultados["curp"] = res_curp

        # NSS
        modulo_nss = NSSModule(captcha_solver=self.solver, mail_reader=self.mail_reader)
        res_nss    = await modulo_nss.consultar(curp=curp, correo=correo)
        resultados["nss"] = res_nss

        # Resumen
        print(f"\n{Fore.GREEN}{'━'*50}")
        print("  RESUMEN FINAL")
        print(f"{'━'*50}{Style.RESET_ALL}")
        print(f"  CURP:  {res_curp.get('curp', '—')}")
        print(f"  NSS:   {res_nss.get('nss', '—')}")
        if res_curp.get("pdf_path"):
            print(f"  PDF:   {res_curp['pdf_path']}")
        print(f"{Fore.GREEN}{'━'*50}{Style.RESET_ALL}\n")

        return resultados

    # ── RFC ───────────────────────────────────────────────────────────────────
    async def tramite_rfc(self, perfil: dict = None) -> dict:
        """Ejecuta consulta de RFC."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: RFC SAT ━━━{Style.RESET_ALL}")
        curp = perfil.get("curp") if perfil else None
        if not curp:
            curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)
        nombre = input("  Nombre (opcional): ").strip() or (perfil or {}).get("nombre", "")
        modulo = RFCModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(curp=curp, nombre=nombre)
        self._mostrar_resultado("RFC", resultado)
        return resultado

    # ── ACTA ─────────────────────────────────────────────────────────────────
    async def tramite_acta(self, perfil: dict = None) -> dict:
        """Ejecuta descarga de Acta de Nacimiento."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Acta de Nacimiento ━━━{Style.RESET_ALL}")
        curp = perfil.get("curp") if perfil else None
        if not curp:
            curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)
        modulo = ActaNacimientoModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(curp=curp)
        self._mostrar_resultado("Acta", resultado)
        return resultado

    # ── PASAPORTE ─────────────────────────────────────────────────────────────
    async def tramite_pasaporte(self, perfil: dict = None) -> dict:
        """Ejecuta cita de pasaporte."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Cita Pasaporte SRE ━━━{Style.RESET_ALL}")
        curp = perfil.get("curp") if perfil else None
        if not curp:
            curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)
        modulo = PasaporteModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(curp=curp, nombre=(perfil or {}).get("nombre", ""))
        self._mostrar_resultado("Pasaporte", resultado)
        return resultado

    # ── SEMANAS ───────────────────────────────────────────────────────────────
    async def tramite_semanas(self, perfil: dict = None) -> dict:
        """Ejecuta consulta de semanas cotizadas."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Semanas Cotizadas IMSS ━━━{Style.RESET_ALL}")
        curp = perfil.get("curp") if perfil else None
        if not curp:
            curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)
        modulo = SemanasModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(curp=curp)
        self._mostrar_resultado("Semanas", resultado)
        return resultado

    # ── CONTROL DE CONFIANZA ──────────────────────────────────────────────────
    async def tramite_control_confianza(self, perfil: dict = None) -> dict:
        """Ejecuta Control de Confianza."""
        print(f"{Fore.YELLOW}⚠ Este trámite requiere intervención manual significativa{Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Control de Confianza SESNSP ━━━{Style.RESET_ALL}")
        curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)
        modulo = ControlConfianzaModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(curp=curp)
        self._mostrar_resultado("Control de Confianza", resultado)
        return resultado

    # ── BURÓ ───────────────────────────────────────────────────────────────────
    async def tramite_buro(self, perfil: dict = None) -> dict:
        """Ejecuta consulta de Buró de Crédito."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Buró de Crédito ━━━{Style.RESET_ALL}")
        rfc = input("  RFC: ").strip().upper()
        curp = input("  CURP: ").strip().upper()
        modulo = BuroModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(rfc=rfc, curp=curp)
        self._mostrar_resultado("Buró", resultado)
        return resultado

    # ── CÍRCULO ────────────────────────────────────────────────────────────────
    async def tramite_circulo(self, perfil: dict = None) -> dict:
        """Ejecuta consulta de Círculo de Crédito."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Círculo de Crédito ━━━{Style.RESET_ALL}")
        rfc = input("  RFC: ").strip().upper()
        curp = input("  CURP: ").strip().upper()
        modulo = CirculoModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(rfc=rfc, curp=curp)
        self._mostrar_resultado("Círculo", resultado)
        return resultado

    # ── CITA INE ──────────────────────────────────────────────────────────────
    async def tramite_cita_ine(self, perfil: dict = None) -> dict:
        """Ejecuta cita INE."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Cita INE ━━━{Style.RESET_ALL}")
        curp = self._pedir_dato("CURP (18 caracteres)", validar=self._validar_curp)
        modulo = CitaINEModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(curp=curp)
        self._mostrar_resultado("Cita INE", resultado)
        return resultado

    # ── CITA SAT ──────────────────────────────────────────────────────────────
    async def tramite_cita_sat(self, perfil: dict = None) -> dict:
        """Ejecuta cita SAT."""
        print(f"\n{Fore.CYAN}━━━ TRÁMITE: Cita SAT ━━━{Style.RESET_ALL}")
        rfc = input("  RFC: ").strip().upper()
        curp = input("  CURP (opcional): ").strip().upper() or ""
        modulo = CitaSATModule(captcha_solver=self.solver)
        resultado = await modulo.consultar(rfc=rfc, curp=curp)
        self._mostrar_resultado("Cita SAT", resultado)
        return resultado

    # ── PERFILES ──────────────────────────────────────────────────────────────
    def gestionar_perfil(self):
        """Menú de gestión de perfiles."""
        print(f"\n{Fore.CYAN}━━━ PERFILES ━━━{Style.RESET_ALL}")
        perfiles = list_profiles()

        opciones = ["1) Guardar nuevo perfil", "2) Cargar perfil existente", "3) Ver perfiles"]
        for op in opciones:
            print(f"  {op}")

        opcion = input("\n  Opción: ").strip()

        if opcion == "1":
            alias   = input("  Nombre del perfil (ej: 'juan_garcia'): ").strip()
            curp    = input("  CURP: ").strip().upper()
            correo  = input("  Correo electrónico: ").strip()
            placa   = input("  Placa del vehículo (opcional): ").strip()
            nombre  = input("  Nombre completo (opcional): ").strip()
            perfil = {
                "curp": curp, "correo": correo,
                "placa": placa, "nombre": nombre,
            }
            save_profile(alias, perfil)
            return perfil

        elif opcion == "2":
            if not perfiles:
                print("  No hay perfiles guardados.")
                return None
            print("\n  Perfiles disponibles:")
            for i, p in enumerate(perfiles, 1):
                print(f"    {i}) {p}")
            sel = input("  Selecciona número: ").strip()
            try:
                alias = perfiles[int(sel) - 1]
                return load_profile(alias)
            except (ValueError, IndexError):
                print("  Selección inválida.")
                return None

        elif opcion == "3":
            if perfiles:
                print(f"\n  Perfiles guardados: {', '.join(perfiles)}")
            else:
                print("  No hay perfiles guardados aún.")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _pedir_dato(self, nombre: str, validar=None, default: str = "") -> str:
        """Solicita un dato al usuario con validación opcional."""
        while True:
            hint = f" (Enter para '{default}')" if default else ""
            val  = input(f"  {nombre}{hint}: ").strip()
            if not val and default:
                return default
            if not val:
                print(f"  {Fore.RED}  El campo '{nombre}' es requerido{Style.RESET_ALL}")
                continue
            if validar and not validar(val):
                print(f"  {Fore.RED}  Formato inválido para '{nombre}'{Style.RESET_ALL}")
                continue
            return val

    def _validar_curp(self, curp: str) -> bool:
        return bool(re.match(r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$", curp.upper()))

    def _mostrar_resultado(self, tipo: str, resultado: dict):
        print(f"\n{Fore.GREEN}{'━'*50}")
        print(f"  {tipo} — RESULTADO")
        print(f"{'━'*50}{Style.RESET_ALL}")
        for k, v in resultado.items():
            if v:
                print(f"  {k.upper()}: {v}")
        print(f"{Fore.GREEN}{'━'*50}{Style.RESET_ALL}\n")


# ─────────────────────────────────────────────────────────────────────────────
async def modo_interactivo():
    agente = Agente()
    print(BANNER)
    print(AYUDA)

    perfil_activo = None
    perfiles = list_profiles()
    if perfiles:
        print(f"  {Fore.CYAN}Perfiles guardados: {', '.join(perfiles)}{Style.RESET_ALL}")
        print()

    while True:
        try:
            cmd = input(f"{Fore.CYAN}tramites>{Style.RESET_ALL} ").strip().lower()

            if not cmd:
                continue
            elif cmd in ("salir", "exit", "q"):
                print("  Hasta luego.")
                break
            elif cmd in ("ayuda", "help", "?"):
                print(AYUDA)
            elif cmd == "curp":
                await agente.tramite_curp(perfil=perfil_activo)
            elif cmd == "nss":
                await agente.tramite_nss(perfil=perfil_activo)
            elif cmd == "rfc":
                await agente.tramite_rfc(perfil=perfil_activo)
            elif cmd == "acta":
                await agente.tramite_acta(perfil=perfil_activo)
            elif cmd == "pasaporte":
                await agente.tramite_pasaporte(perfil=perfil_activo)
            elif cmd == "semanas":
                await agente.tramite_semanas(perfil=perfil_activo)
            elif cmd in ("control_confianza", "control", "confianza"):
                await agente.tramite_control_confianza(perfil=perfil_activo)
            elif cmd in ("buro", "buro_credito"):
                await agente.tramite_buro(perfil=perfil_activo)
            elif cmd in ("circulo", "circulo_credito"):
                await agente.tramite_circulo(perfil=perfil_activo)
            elif cmd in ("cita_ine", "ine"):
                await agente.tramite_cita_ine(perfil=perfil_activo)
            elif cmd in ("cita_sat", "sat"):
                await agente.tramite_cita_sat(perfil=perfil_activo)
            elif cmd in ("ambos", "todo", "nss+curp", "curp+nss"):
                await agente.tramite_ambos(perfil=perfil_activo)
            elif cmd == "perfil":
                p = agente.gestionar_perfil()
                if p:
                    perfil_activo = p
                    print(f"  {Fore.GREEN}Perfil cargado [OK]{Style.RESET_ALL}")
            else:
                # Interpretar lenguaje natural básico
                if "curp" in cmd and "nss" in cmd:
                    await agente.tramite_ambos(perfil=perfil_activo)
                elif "curp" in cmd:
                    await agente.tramite_curp(perfil=perfil_activo)
                elif "nss" in cmd or "seguro" in cmd or "imss" in cmd:
                    await agente.tramite_nss(perfil=perfil_activo)
                else:
                    print(f"  Comando '{cmd}' no reconocido. Escribe 'ayuda'.")

        except KeyboardInterrupt:
            print("\n  Interrumpido. Escribe 'salir' para salir.")
        except Exception as e:
            print(f"  {Fore.RED}Error: {e}{Style.RESET_ALL}")


async def modo_directo(args):
    """Modo sin interacción para scripts y automatización."""
    agente = Agente()
    perfil = None

    if args.perfil:
        perfil = load_profile(args.perfil)
        if not perfil:
            print(f"Perfil '{args.perfil}' no encontrado.")
            sys.exit(1)

    if args.tramite == "curp":
        curp = args.curp or (perfil and perfil.get("curp"))
        if not curp:
            print("Error: se requiere --curp")
            sys.exit(1)
        await CURPModule(captcha_solver=agente.solver).consultar(curp=curp)

    elif args.tramite == "nss":
        curp   = args.curp   or (perfil and perfil.get("curp"))
        correo = args.correo or (perfil and perfil.get("correo"))
        if not curp or not correo:
            print("Error: se requieren --curp y --correo")
            sys.exit(1)
        mail_reader = agente.mail_reader
        await NSSModule(captcha_solver=agente.solver, mail_reader=mail_reader).consultar(
            curp=curp, correo=correo
        )

    elif args.tramite == "rfc":
        curp = args.curp or (perfil and perfil.get("curp"))
        if not curp:
            print("Error: se requiere --curp")
            sys.exit(1)
        await RFCModule(captcha_solver=agente.solver).consultar(curp=curp)

    elif args.tramite == "acta_nacimiento":
        curp = args.curp or (perfil and perfil.get("curp"))
        if not curp:
            print("Error: se requiere --curp")
            sys.exit(1)
        await ActaNacimientoModule(captcha_solver=agente.solver).consultar(curp=curp)

    elif args.tramite == "pasaporte":
        curp = args.curp or (perfil and perfil.get("curp"))
        if not curp:
            print("Error: se requiere --curp")
            sys.exit(1)
        await PasaporteModule(captcha_solver=agente.solver).consultar(curp=curp)

    elif args.tramite == "semanas":
        curp = args.curp or (perfil and perfil.get("curp"))
        if not curp:
            print("Error: se requiere --curp")
            sys.exit(1)
        await SemanasModule(captcha_solver=agente.solver).consultar(curp=curp)

    elif args.tramite == "control_confianza":
        curp = args.curp or (perfil and perfil.get("curp"))
        if not curp:
            print("Error: se requiere --curp")
            sys.exit(1)
        await ControlConfianzaModule(captcha_solver=agente.solver).consultar(curp=curp)

    elif args.tramite == "buro":
        rfc = args.rfc or input("RFC: ").strip().upper()
        curp = args.curp or input("CURP: ").strip().upper()
        await BuroModule(captcha_solver=agente.solver).consultar(rfc=rfc, curp=curp)

    elif args.tramite == "circulo":
        rfc = args.rfc or input("RFC: ").strip().upper()
        curp = args.curp or input("CURP: ").strip().upper()
        await CirculoModule(captcha_solver=agente.solver).consultar(rfc=rfc, curp=curp)

    elif args.tramite == "cita_ine":
        curp = args.curp or (perfil and perfil.get("curp"))
        if not curp:
            print("Error: se requiere --curp")
            sys.exit(1)
        await CitaINEModule(captcha_solver=agente.solver).consultar(curp=curp)

    elif args.tramite == "cita_sat":
        rfc = args.rfc or input("RFC: ").strip().upper()
        curp = args.curp or ""
        await CitaSATModule(captcha_solver=agente.solver).consultar(rfc=rfc, curp=curp)


def _handle_shutdown(signum, frame):
    """Graceful shutdown — cierra tareas asíncronas sin corrupción.

    Pilar 5 — Fiabilidad & Resiliencia: evita estado inconsistente.
    """
    print(f"\n{Fore.YELLOW}[!]  Cerrando graceful... (Ctrl+C otra vez para forzar){Style.RESET_ALL}")
    for task in asyncio.all_tasks():
        task.cancel()


def main():
    signal.signal(signal.SIGINT, _handle_shutdown)

    parser = argparse.ArgumentParser(description="Agente de Trámites GOB.MX")
    parser.add_argument("--tramite", choices=[
        "curp", "nss", "ambos", "rfc", "acta_nacimiento",
        "pasaporte", "semanas", "control_confianza",
        "buro", "circulo", "cita_ine", "cita_sat",
    ], help="Trámite a realizar")
    parser.add_argument("--curp",    help="CURP de 18 caracteres")
    parser.add_argument("--rfc",     help="RFC para trámites que lo requieran")
    parser.add_argument("--correo",  help="Correo electrónico")
    parser.add_argument("--perfil",  help="Alias de perfil guardado")
    parser.add_argument("--list-tramites", action="store_true", help="Listar todos los trámites disponibles")
    args = parser.parse_args()

    _validar_config()

    if args.list_tramites:
        _listar_tramites()
        return

    try:
        if args.tramite or args.perfil:
            asyncio.run(modo_directo(args))
        else:
            asyncio.run(modo_interactivo())
    except KeyboardInterrupt:
        print(f"\n{Fore.GREEN}[OK]  Sesión cerrada.{Style.RESET_ALL}")
    except asyncio.CancelledError:
        print(f"\n{Fore.GREEN}[OK]  Tareas canceladas graceful.{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
