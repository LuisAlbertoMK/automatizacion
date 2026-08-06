"""Tests para src/utils/cache.py — TramiteCache singleton LRU+TTL.

Cobertura objetivo: 100% de src/utils/cache.py
Técnicas: unit testing + edge cases + LRU/TTL eviction + input sanitization
"""
import time

import pytest

from src.utils.cache import TramiteCache


@pytest.fixture(autouse=True)
def reset_cache():
    """Resetea el singleton antes de cada test."""
    TramiteCache.reset_instance()
    yield
    TramiteCache.reset_instance()


class TestSingleton:
    """Singleton pattern tests."""

    def test_get_instance_returns_same_object(self):
        """get_instance debe devolver siempre la misma instancia."""
        a = TramiteCache.get_instance()
        b = TramiteCache.get_instance()
        assert a is b

    def test_reset_instance_clears_singleton(self):
        """reset_instance debe permitir crear una nueva instancia."""
        a = TramiteCache.get_instance()
        TramiteCache.reset_instance()
        b = TramiteCache.get_instance()
        assert a is not b

    def test_default_config(self):
        """La configuración por default debe ser 50 entries / 1800s TTL."""
        c = TramiteCache.get_instance()
        assert c.max_entries == 50
        assert c.size == 0


class TestMakeKey:
    """Tests de generación de claves."""

    def test_same_inputs_same_key(self):
        """Mismo tipo + inputs → misma clave."""
        k1 = TramiteCache.make_key("curp", ("123456789012345678",))
        k2 = TramiteCache.make_key("curp", ("123456789012345678",))
        assert k1 == k2

    def test_different_tramite_type_different_key(self):
        """Diferente tramite_type → clave distinta aunque inputs sean iguales."""
        k1 = TramiteCache.make_key("curp", ("123456789012345678",))
        k2 = TramiteCache.make_key("nss", ("123456789012345678",))
        assert k1 != k2

    def test_different_inputs_different_key(self):
        """Inputs distintos → clave distinta."""
        k1 = TramiteCache.make_key("curp", ("123456789012345678",))
        k2 = TramiteCache.make_key("curp", ("876543210987654321",))
        assert k1 != k2

    def test_key_is_hex_32_chars(self):
        """La clave debe ser 32 chars hexadecimales."""
        k = TramiteCache.make_key("curp", ("test",))
        assert len(k) == 32
        int(k, 16)  # debe ser parseable como hex

    def test_input_truncation_200_chars(self):
        """Inputs >200 chars se truncan (evita claves gigantes)."""
        k1 = TramiteCache.make_key("curp", ("A" * 500,))
        k2 = TramiteCache.make_key("curp", ("A" * 200,))
        # Después de truncar, "A"*200 vs "A"*200 truncado → iguales
        assert k1 == k2

    def test_control_chars_stripped(self):
        """Caracteres de control eliminados (sanitización)."""
        k1 = TramiteCache.make_key("curp", ("AB\nC\r\tD",))
        k2 = TramiteCache.make_key("curp", ("ABCD",))
        assert k1 == k2


class TestGetSet:
    """Tests de operaciones get/set."""

    def test_get_missing_returns_none(self):
        """get en clave inexistente devuelve None."""
        c = TramiteCache.get_instance()
        assert c.get("curp", ("123",)) is None

    def test_set_then_get(self):
        """set + get devuelve el valor almacenado."""
        c = TramiteCache.get_instance()
        result = {"curp": "123456789012345678", "nombre": "Test"}
        c.set("curp", ("123456789012345678",), result)
        assert c.get("curp", ("123456789012345678",)) == result

    def test_overwrite_value(self):
        """set sobre una clave existente sobreescribe el valor."""
        c = TramiteCache.get_instance()
        c.set("nss", ("123",), {"nss": "old"})
        assert c.get("nss", ("123",))["nss"] == "old"
        c.set("nss", ("123",), {"nss": "new"})
        assert c.get("nss", ("123",))["nss"] == "new"


class TestTTL:
    """Tests de expiración por TTL."""

    def test_value_expires_after_ttl(self):
        """El valor expira después del TTL y get devuelve None."""
        c = TramiteCache.get_instance(max_entries=10, ttl=1)
        c.set("curp", ("x",), "data", ttl=1)
        assert c.get("curp", ("x",)) == "data"
        time.sleep(1.1)
        assert c.get("curp", ("x",)) is None

    def test_ttl_override(self):
        """set permite overridear el TTL del singleton."""
        c = TramiteCache.get_instance(ttl=1000)
        c.set("nss", ("y",), "data", ttl=1)
        time.sleep(1.1)
        assert c.get("nss", ("y",)) is None

    def test_expired_entry_evicted_on_next_get(self):
        """Una entrada expirada se elimina del cache en el siguiente get."""
        c = TramiteCache.get_instance(max_entries=10, ttl=1)
        c.set("curp", ("z",), "data", ttl=1)
        time.sleep(1.1)
        c.get("curp", ("z",))  # debería devolver None y limpiar
        assert c.size == 0


class TestLRU:
    """Tests de evictión LRU."""

    def test_lru_evicts_oldest(self):
        """Cuando se supera max_entries, se evita la entrada más antigua (LRU)."""
        c = TramiteCache.get_instance(max_entries=2, ttl=1000)
        c.set("a", ("1",), "val_a")
        c.set("b", ("2",), "val_b")
        # Accesar 'a' para promoverlo (más reciente)
        assert c.get("a", ("1",)) == "val_a"
        # Insertar 'c' — debe evictar 'b' (la menos reciente), no 'a'
        c.set("c", ("3",), "val_c")
        assert c.get("a", ("1",)) == "val_a"  # 'a' sigue vivo
        assert c.get("b", ("2",)) is None    # 'b' fue evictada

    def test_lru_order_updated_on_get(self):
        """Un get promueve la entrada en el orden LRU."""
        c = TramiteCache.get_instance(max_entries=2, ttl=1000)
        c.set("a", ("1",), "val_a")
        c.set("b", ("2",), "val_b")
        # Promover 'a'
        c.get("a", ("1",))
        # Insertar 'c' — evcta 'b' (least recently used)
        c.set("c", ("3",), "val_c")
        assert c.get("a", ("1",)) == "val_a"
        assert c.get("b", ("2",)) is None


class TestClearSize:
    """Tests de clear + size."""

    def test_clear_returns_count(self):
        """clear devuelve el número de entradas borradas."""
        c = TramiteCache.get_instance(max_entries=100, ttl=1000)
        c.set("a", ("1",), "v1")
        c.set("b", ("2",), "v2")
        assert c.clear() == 2
        assert c.size == 0

    def test_size_counts_active_entries(self):
        """size cuenta solo entradas no expiradas."""
        c = TramiteCache.get_instance(max_entries=100, ttl=1000)
        c.set("a", ("1",), "v1", ttl=1)
        c.set("b", ("2",), "v2", ttl=1000)
        assert c.size == 2
        time.sleep(1.1)
        # size limpia entradas expiradas
        assert c.size == 1


class TestValidation:
    """Tests de validación de parámetros."""

    def test_max_entries_must_be_positive(self):
        """max_entries < 1 debe lanzar ValueError."""
        with pytest.raises(ValueError, match="max_entries"):
            TramiteCache(max_entries=0)

    def test_ttl_must_be_positive(self):
        """ttl < 1 debe lanzar ValueError."""
        with pytest.raises(ValueError, match="ttl"):
            TramiteCache(ttl=0)

    def test_set_ttl_must_be_positive(self):
        """set con ttl < 1 debe lanzar ValueError."""
        c = TramiteCache.get_instance()
        with pytest.raises(ValueError, match="ttl"):
            c.set("a", ("1",), "v", ttl=0)
