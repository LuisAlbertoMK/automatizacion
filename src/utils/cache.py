"""Cache de resultados de trámites.

TramiteCache: singleton LRU+TTL thread-safe para evitar duplicación
de trabajo (launch browser, CAPTCHA, scraping) cuando un mismo trámite
se ejecuta múltiples veces con las mismas entradas dentro del TTL.

Patrón: singleton con asyncio.Lock (misma convención que ``_fernet_cache``
en storage.py). La clave es sha256(tramite_type + sanitized_inputs).
"""
from __future__ import annotations

import asyncio
import hashlib
import time
from collections import OrderedDict
from typing import Any, Optional

_DEFAULT_TTL = 1800  # 30 minutos
_MAX_ENTRIES = 50


class TramiteCache:
    """Cache singleton con LRU eviction + TTL.

    Args:
        max_entries: Límite máximo de entradas (LRU evicta las más viejas).
        ttl: Tiempo de vida en segundos (default 30 min).
    """

    _instance: Optional["TramiteCache"] = None
    _init_lock = asyncio.Lock()
    _lock = asyncio.Lock()

    def __init__(self, max_entries: int = _MAX_ENTRIES, ttl: int = _DEFAULT_TTL) -> None:
        if max_entries < 1:
            raise ValueError(f"max_entries debe ser ≥1, recibido {max_entries}")
        if ttl < 1:
            raise ValueError(f"ttl debe ser ≥1, recibido {ttl}")
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_entries = max_entries
        self._ttl = ttl

    @classmethod
    def get_instance(
        cls, *, max_entries: int = _MAX_ENTRIES, ttl: int = _DEFAULT_TTL
    ) -> "TramiteCache":
        """Devuelve el singleton (thread-safe init)."""
        if cls._instance is None:
            cls._instance = cls(max_entries=max_entries, ttl=ttl)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Resetea el singleton — usar en tests."""
        cls._instance = None

    @staticmethod
    def _sanitize_inputs(inputs: tuple) -> str:
        """Convierte inputs a string sanitizado para el hash de clave.

        Trunca cada elemento a 200 chars para evitar claves gigantes
        y previene cache poisoning por inputs maliciosos.
        """
        safe_parts = []
        for inp in inputs:
            s = str(inp)
            if len(s) > 200:
                s = s[:200]
            # Elimina caracteres de control
            s = "".join(c for c in s if c.isprintable())
            safe_parts.append(s)
        return "|".join(safe_parts)

    @classmethod
    def make_key(cls, tramite_type: str, inputs: tuple) -> str:
        """Genera una clave sha256 de 32 hex chars a partir del tipo + inputs."""
        raw = f"{tramite_type}:{cls._sanitize_inputs(inputs)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def get(self, tramite_type: str, inputs: tuple) -> Optional[Any]:
        """Obtiene un resultado cacheado. Devuelve ``None`` si no existe o expiró."""
        key = self.make_key(tramite_type, inputs)
        if key not in self._data:
            return None
        value, expires_at = self._data[key]
        if time.monotonic() > expires_at:
            # Expirado — evict
            del self._data[key]
            return None
        # LRU: mover al final (más reciente)
        self._data.move_to_end(key)
        return value

    def set(self, tramite_type: str, inputs: tuple, value: Any, ttl: Optional[int] = None) -> None:
        """Almacena un resultado con TTL opcional (override)."""
        key = self.make_key(tramite_type, inputs)
        _ttl = ttl if ttl is not None else self._ttl
        if _ttl < 1:
            raise ValueError(f"ttl debe ser ≥1, recibido {_ttl}")
        expires_at = time.monotonic() + _ttl
        self._data[key] = (value, expires_at)
        self._data.move_to_end(key)
        # LRU eviction
        while len(self._data) > self._max_entries:
            self._data.popitem(last=False)

    def clear(self) -> int:
        """Limpia el cache. Devuelve el número de entradas borradas."""
        count = len(self._data)
        self._data.clear()
        return count

    @property
    def size(self) -> int:
        """Número de entradas activas (no expiradas)."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._data.items() if now > exp]
        for k in expired:
            del self._data[k]
        return len(self._data)

    @property
    def max_entries(self) -> int:
        return self._max_entries
