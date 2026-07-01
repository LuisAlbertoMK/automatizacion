"""
utils/secrets_manager.py
Gestor centralizado de secrets con Windows Credential Manager + fallback a env vars.

Flujo:
  1. load_dotenv("config.env") carga vars desde archivo (como hoy)
  2. init_secrets() sobreescribe las sensibles desde Windows Credential Manager
  3. Todo el código existente sigue usando os.getenv() sin cambios

Uso:
  from utils.secrets_manager import init_secrets, store_all
  init_secrets()  # después de load_dotenv()
  store_all()     # una sola vez para migrar secrets a Credential Manager
"""

import os

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

SERVICE_NAME = "agente-tramites-gobmx"

# Secrets que van al Credential Manager (NO incluir config NO sensible)
SECRET_KEYS = [
    "CAPTCHA_API_KEY",
    "IMAP_EMAIL",
    "IMAP_PASSWORD",
    "STORAGE_KEY",
    "ANTHROPIC_API_KEY",
]


def get_secret(key: str, default: str = "") -> str:
    """Obtiene un secret: Credential Manager primero, env var como fallback."""
    if KEYRING_AVAILABLE:
        try:
            stored = keyring.get_password(SERVICE_NAME, key)
            if stored:
                return stored
        except Exception:
            pass
    return os.getenv(key, default)


def init_secrets() -> None:
    """Carga secrets desde Credential Manager a os.environ (post-load_dotenv)."""
    if not KEYRING_AVAILABLE:
        return  # Sin keyring, todo depende de config.env (comportamiento legacy)
    for key in SECRET_KEYS:
        try:
            stored = keyring.get_password(SERVICE_NAME, key)
            if stored:
                os.environ[key] = stored
        except Exception:
            pass  # Si falla keyring, se queda el valor de config.env


def store_secret(key: str, value: str | None = None) -> bool:
    """Guarda un secret en Credential Manager. Si value es None, lee de os.environ."""
    if not KEYRING_AVAILABLE:
        print("  [SECRETS] keyring no instalado. Instalá: pip install keyring")
        return False
    val = value or os.getenv(key, "")
    if not val:
        print(f"  [SECRETS] {key} está vacío — no se guarda")
        return False
    try:
        keyring.set_password(SERVICE_NAME, key, val)
        print(f"  [SECRETS] ✅ {key} guardado en Windows Credential Manager")
        return True
    except Exception as e:
        print(f"  [SECRETS] ❌ Error guardando {key}: {e}")
        return False


def store_all() -> None:
    """Migra todos los secrets desde config.env a Windows Credential Manager."""
    print("  [SECRETS] Migrando secrets a Windows Credential Manager...")
    ok = 0
    for key in SECRET_KEYS:
        val = os.getenv(key, "")
        if val and val not in ("tu_api_key_aqui", "cambia_esta_clave_secreta_32chars!"):
            if store_secret(key, val):
                ok += 1
    print(f"  [SECRETS] {ok}/{len(SECRET_KEYS)} secrets migrados")

    if ok > 0:
        print()
        print("  ⚠️  Ahora podés borrar los valores reales de config.env")
        print("     dejando solo las vars NO sensibles (OUTPUT_DIR, TIMEOUT, etc.)")
        print("     o migrar completamente a ambiente via:\n")
        print("       $env:CAPTCHA_API_KEY=\"tu_key\"  # PowerShell")
        print("       export CAPTCHA_API_KEY=tu_key    # Bash (WSL)")


def main_cli():
    """CLI interactivo para gestionar secrets."""
    import argparse

    parser = argparse.ArgumentParser(description="Gestor de secrets")
    parser.add_argument("action", choices=["store", "store-all", "list", "delete"],
                       help="Acción a realizar")
    parser.add_argument("--key", help="Nombre del secret")
    parser.add_argument("--value", help="Valor del secret (opcional, si omite se pide)")
    args = parser.parse_args()

    if args.action == "store-all":
        store_all()
        return

    if args.action == "list":
        if not KEYRING_AVAILABLE:
            print("keyring no disponible")
            return
        for key in SECRET_KEYS:
            val = keyring.get_password(SERVICE_NAME, key)
            masked = val[:4] + "****" if val else "(no configurado)"
            print(f"  {key}: {masked}")
        return

    if args.action == "delete":
        if not KEYRING_AVAILABLE:
            print("keyring no disponible")
            return
        if not args.key:
            print("Especificá --key")
            return
        try:
            keyring.delete_password(SERVICE_NAME, args.key)
            print(f"  ✅ {args.key} eliminado")
        except Exception as e:
            print(f"  {e}")
        return

    # store individual
    if not args.key:
        print("Especificá --key")
        return
    value = args.value
    if not value:
        value = input(f"  Valor para {args.key}: ").strip()
    store_secret(args.key, value)


if __name__ == "__main__":
    main_cli()
