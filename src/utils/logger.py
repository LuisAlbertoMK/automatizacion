"""
utils/logger.py
Logging centralizado y métricas de trámites.
Reemplaza los print() dispersos por un sistema estructurado.
"""

import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from colorama import Fore, Style


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
        "info":    "ℹ",
        "success": "✅",
        "warning": "⚠",
        "error":   "❌",
        "debug":   "🔍",
    }

    def __init__(self, modulo: str, verbose: bool = False):
        self.modulo = modulo
        self.verbose = verbose or os.getenv("VERBOSE", "false").lower() == "true"

        # Python logging estándar (a archivo)
        self._logger = logging.getLogger(f"tramites.{modulo}")
        if not self._logger.handlers:
            fh = logging.FileHandler(LOG_DIR / "tramites.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
            ))
            self._logger.addHandler(fh)
            self._logger.setLevel(logging.DEBUG)

    def _print(self, level: str, msg: str):
        color = self.COLORS.get(level, "")
        icon = self.ICONS.get(level, "")
        print(f"  {color}[{self.modulo}] {icon} {msg}{Style.RESET_ALL}")

    def info(self, msg: str):
        self._print("info", msg)
        self._logger.info(msg)

    def success(self, msg: str):
        self._print("success", msg)
        self._logger.info(f"SUCCESS: {msg}")

    def warn(self, msg: str):
        self._print("warning", msg)
        self._logger.warning(msg)

    def error(self, msg: str):
        self._print("error", msg)
        self._logger.error(msg)

    def debug(self, msg: str):
        if self.verbose:
            self._print("debug", msg)
        self._logger.debug(msg)


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
            pass
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
                        pass
        except Exception:
            pass

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
