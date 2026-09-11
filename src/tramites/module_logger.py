"""Logging estructurado para módulos de trámites.

Extraído de src/tramites/base.py (incremento 3). Replica el
comportamiento EXACTO de BaseModule.log/debug/warn/error:

- Dual path: logger estructurado (TramiteLogger vía get_logger) vs
  stdout/print cuando no hay logger.
- Gate VERBOSE solo en el fallback stdout de debug; cuando hay
  logger, debug siempre delega a logger.debug sin gate (el gate
  vive dentro de TramiteLogger si aplica).
- Formato de mensajes stdout idéntico al original.

Los helpers son puros: reciben `logger`, `module_name` y flags por
parámetros explícitos y nunca leen globales. Los wrappers en
BaseModule leen `os.getenv("VERBOSE")` en call-time y lo pasan
explícito, para que los parches sobre `src.tramites.base.os.getenv`
sigan funcionando.
"""


def emit_log(logger, module_name: str, msg: str):
    """Info genérica."""
    if logger:
        logger.info(msg)
    else:
        print(f"  [{module_name}] {msg}")


def emit_debug(logger, module_name: str, msg: str, verbose: bool = False):
    """Debug (solo si VERBOSE en fallback stdout)."""
    if logger:
        logger.debug(msg)
    elif verbose:
        print(f"  [DEBUG][{module_name}] {msg}")


def emit_warn(logger, module_name: str, msg: str):
    """Advertencia."""
    if logger:
        logger.warn(msg)
    else:
        print(f"  [{module_name}] \u26a0 {msg}")


def emit_error(logger, module_name: str, msg: str):
    """Error."""
    if logger:
        logger.error(msg)
    else:
        print(f"  [{module_name}] \u274c {msg}")
