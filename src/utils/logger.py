"""
utils/logger.py
Logging centralizado y métricas de trámites.
Reemplaza los print() dispersos por un sistema estructurado.
"""

import json
import logging
import logging.handlers
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from colorama import Fore, Style

logger = logging.getLogger(__name__)

# ── Directorio de logs ──────────────────────────────────────────────────
LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
LOG_DIR.mkdir(exist_ok=True)

METRICS_FILE = LOG_DIR / "metricas_tramites.jsonl"


# ── Logger con colores ──────────────────────────────────────────────────
class TramiteLogger:
    """Logger con niveles, colores y persistencia."""

    COLORS = {
        "info":    Fore.CYAN,
        "success": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error":   Fore.RED,
        "debug":   Fore.WHITE,
    }
    ICONS = {
        "info":    "[i]",
        "success": "[OK]",
        "warning": "[!]",
        "error":   "[ERR]",
        "debug":   "🔍",
    }

    def __init__(self, modulo: str, verbose: bool = False):
        self.modulo = modulo
        self.verbose = verbose or os.getenv("VERBOSE", "false").lower() == "true"

        # Python logging estándar (a archivo)
        self._logger = logging.getLogger(f"tramites.{modulo}")
        if not self._logger.handlers:
            fh = logging.handlers.RotatingFileHandler(
                LOG_DIR / "tramites.log",
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
            ))
            self._logger.addHandler(fh)
            self._logger.setLevel(logging.DEBUG)

    # Patrones PII para sanitización automática en archivo de log
    _PII_PATTERNS = [
        (re.compile(r'\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b'), lambda m: f"{m.group()[:4]}****"),
        (re.compile(r'\b\d{11}\b'), lambda m: f"{m.group()[:5]}******"),
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), lambda m: f"{m.group()[0]}***@{m.group().split('@')[1]}"),
    ]

    @staticmethod
    def _sanitize(msg: str) -> str:
        """Reemplaza CURP, NSS y email en el mensaje antes de escribirlo a log."""
        for pattern, repl in TramiteLogger._PII_PATTERNS:
            msg = pattern.sub(repl, msg)
        return msg

    def _print(self, level: str, msg: str):
        color = self.COLORS.get(level, "")
        icon = self.ICONS.get(level, "")
        print(f"  {color}[{self.modulo}] {icon} {msg}{Style.RESET_ALL}")

    def info(self, msg: str):
        self._print("info", msg)
        self._logger.info(self._sanitize(msg))

    def success(self, msg: str):
        self._print("success", msg)
        self._logger.info(self._sanitize(f"SUCCESS: {msg}"))

    def warn(self, msg: str):
        self._print("warning", msg)
        self._logger.warning(self._sanitize(msg))

    def error(self, msg: str, exc_info: bool = False):
        self._print("error", msg)
        self._logger.error(self._sanitize(msg), exc_info=exc_info)

    def debug(self, msg: str):
        if self.verbose:
            self._print("debug", msg)
        self._logger.debug(self._sanitize(msg))

    def info_pii(self, msg: str, pii_value: str, pii_type: str = "curp"):
        """Info con PII visible en stdout pero sanitizada en archivo."""
        from src.utils.pii import sanitize_pii as _san  # noqa: PLC0415
        sanitized = _san(pii_value, pii_type)
        safe_msg = msg.replace(pii_value, sanitized)
        self._print("info", safe_msg)
        # En archivo va siempre sanitizado
        self._logger.info(self._sanitize(msg))


# ── Métricas de trámites ────────────────────────────────────────────────
class TramiteMetrics:
    """Registra métricas de cada trámite para auto-mejora."""

    def __init__(self):
        self._start: Optional[float] = None
        self._tramite: str = ""

    def start(self, tramite: str):
        self._tramite = tramite
        self._start = time.time()

    def finish(self, success: bool, extra: dict = None):
        if not self._start:
            return
        elapsed = time.time() - self._start
        record = {
            "timestamp": datetime.now().isoformat(),
            "tramite": self._tramite,
            "success": success,
            "elapsed_s": round(elapsed, 1),
            **(extra or {}),
        }
        try:
            with open(METRICS_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            logger.debug("Error limpiando logs viejos")
        self._start = None
        return record

    @staticmethod
    def resumen() -> dict:
        """Retorna resumen de métricas."""
        if not METRICS_FILE.exists():
            return {"total": 0}
        records = []
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        logger.debug("Error rotando archivo")
        except Exception:
            logger.debug("Error en rotacion de logs")

        if not records:
            return {"total": 0}

        total = len(records)
        ok = sum(1 for r in records if r.get("success"))
        avg_time = sum(r.get("elapsed_s", 0) for r in records) / total

        by_type = {}
        for r in records:
            t = r.get("tramite", "?")
            by_type.setdefault(t, {"total": 0, "ok": 0})
            by_type[t]["total"] += 1
            if r.get("success"):
                by_type[t]["ok"] += 1

        return {
            "total": total,
            "exitosos": ok,
            "tasa_exito": f"{ok/total*100:.0f}%",
            "tiempo_promedio_s": round(avg_time, 1),
            "por_tipo": by_type,
        }


# ── Instancias globales ────────────────────────────────────────────────
metrics = TramiteMetrics()


def get_logger(modulo: str) -> TramiteLogger:
    return TramiteLogger(modulo)
