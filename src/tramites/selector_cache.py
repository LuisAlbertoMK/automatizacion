"""Caché LRU de selectores exitosos para trámites.

Extraído de src/tramites/base.py (incremento 4). Replica el
comportamiento EXACTO del bloque original en BaseModule:

- Clave: ``str(tuple(selectors))`` (misma fórmula en fill_field/click_first).
- Capacidad: 512 entradas, evicción LRU determinista vía OrderedDict
  (``move_to_end`` + ``popitem(last=False)``).
- Sin ``move_to_end`` en lectura: el original solo reordena en escritura.

Los helpers son puros: reciben el ``OrderedDict`` por parámetro
explícito y nunca tocan estado global. BaseModule mantiene
``self._selector_cache`` como OrderedDict plano (compatibilidad con
tests y módulos que lo acceden como atributo directo) y delega
solo la escritura/limpieza/clave a estos helpers.
"""

from collections import OrderedDict

SELECTOR_CACHE_CAPACITY = 512


def make_cache_key(selectors: list) -> str:
    """Construye la clave de caché (idéntica a la original)."""
    return str(tuple(selectors))


def store_selector(cache: OrderedDict, cache_key: str, sel: str) -> None:
    """Guarda selector exitoso con evicción LRU (máx 512)."""
    cache[cache_key] = sel
    cache.move_to_end(cache_key)
    if len(cache) > SELECTOR_CACHE_CAPACITY:
        cache.popitem(last=False)


def clear_cache(cache: OrderedDict) -> None:
    """Limpia el caché de selectores."""
    cache.clear()
