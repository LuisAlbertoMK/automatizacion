# ADR-004: Random salt para campos sensibles (M6)

**Fecha:** 2026-08-06  
**Estado:** ✅ Aceptada e implementada  
**Decisión:** Reemplazar salt determinístico (`hashlib.sha256(alias)[:16]`) con `secrets.token_hex(16)[:16]` por campo, añadir `storage_needs_migration()` para lazy migration.

## Contexto

ANALISIS-SEGURIDAD.md M6 identificó que `_hash_sensitive()` en `storage.py:142` usaba
un salt determinístico derivado del alias: `hashlib.sha256(alias.encode()).hexdigest()[:16]`.

**Riesgo:** Si un atacante accede al archivo de storage, conoce el salt para cada perfil
(derivable del alias). Esto debilita el bcrypt kdf a un ataque de diccionario offline.

## Opciones evaluadas

| # | Enfoque | Pros | Contras | ICE |
|---|---------|------|---------|-----|
| **A1 (elegido)** | `secrets.token_hex(16)[:16]` por campo + `storage_needs_migration()` | ✅ Simple, ✅ cryptographically correct, ✅ migración detectada | ⚠️ No re-hashea sin valor original (lazy migration) | 5×10×5 = 2.5 |
| **A2** | Combinar persistent salt (`_get_salt()`) + field name | ✅ Reutiliza infra existente | ⚠️ Aún parcialmente determinístico | 4×9×4 = 1.4 |
| **A3** | bcrypt.hashpw (incluye salt en hash) | ✅ Salt embebido en hash | ❌ Cambia API de verify_sensitive | 3×8×2 = 0.5 |

## Decisión: A1

### Cambios en `src/utils/storage.py`:
1. `_hash_sensitive()`: `salt = secrets.token_hex(16)[:16]` (era `hashlib.sha256(alias.encode())[:16]`)
2. `_is_deterministic_salt(salt, alias)`: detecta salt legacy (compara contra `sha256(alias)[:16]`)
3. `storage_needs_migration(alias)`: retorna True si algún campo `_xxx_salt` usa salt determinístico

### Migration strategy (lazy):
- Profiles nuevos: usan salt aleatorio automáticamente
- Profiles legacy: `verify_sensitive()` sigue funcionando (usa salt almacenado)
- `storage_needs_migration()` permite detectar y migrar en UI/CLI
- La migración requiere re-ingresar valores (no se puede re-hashear un hash)

### Tests (`tests/test_storage.py` — +10 tests):
- Salt no determinístico entre llamadas
- verify_sensitive funciona con salt aleatorio
- Salt formato (hex 16 chars)
- _is_deterministic_salt: detecta old, rechaza random
- storage_needs_migration: detecta old salt, retorna False para random, retorna False para perfil inexistente

## Consecuencias
- ✅ Security: 2 perfiles con mismo alias ya no comparten salt
- ✅ No breaking change: verify_sensitive usa salt almacenado (backward compatible)
- ✅ 32 storage tests, 100% coverage
- Migration path documentada via storage_needs_migration()
