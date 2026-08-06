# ADR-005: PII sanitization en stdout (M2)

**Fecha:** 2026-08-06  
**Estado:** ✅ Aceptada e implementada  
**Decisión:** Añadir `SANITIZE_STDOUT` env var a `TramiteLogger._print()` para sanitizar PII en stdout cuando está habilitado.

## Contexto

ANALISIS-SEGURIDAD.md M2 identificó que `TramiteLogger._print()` imprime mensajes **unsanitizados** a stdout.
En entornos de producción/Docker, stdout se captura en container logs → PII (CURP, NSS, email)
exfiltrable vía logs de contenedor.

81 `print()` calls encontrados en `src/tramites/` — la mayoría son UI/menu (no PII directo),
pero el logger core (`_print`) es el punto de enfoque.

## Opciones evaluadas

| # | Enfoque | Pros | Contras | ICE |
|---|---------|------|---------|-----|
| **A1 (elegido)** | `SANITIZE_STDOUT` env var → `_sanitize()` aplicada en `_print()` | ✅ Configurable, ✅ no rompe UX dev, ✅ low effort | ⚠️ Requiere configuración en prod | 8×10×3 = 2.4 |
| **A2** | Sanitizar siempre stdout | ✅ Siempre seguro | ❌ Rompe UX — usuario no ve sus datos | 8×8×2 = 1.3 |
| **A3** | Reemplazar 81 print() con TramiteLogger | ✅ Consistencia total | ❌ Esfuerzo muy alto, riesgo de regresión | 6×9×1 = 0.6 |

## Decisión: A1

### Cambios en `src/utils/logger.py`:
- `_print()` verifica `SANITIZE_STDOUT` env (default "false")
- Si "true": aplica `self._sanitize(msg)` antes de `print()`
- Si "false": comportamiento original (PII visible en stdout para UX de desarrollo)

### Tests (`tests/test_logger.py` — +2 tests):
- `test_print_sanitize_env_masks_pii`: con SANITIZE_STDOUT=true, CURP/NSS/email enmascarados
- `test_print_no_sanitize_by_default`: sin env var, PII visible (default dev behavior)

## Consecuencias
- ✅ Dev: usuario ve PII (UX intacta)
- ✅ Prod: `SANITIZE_STDOUT=true` en Docker/CI → PII enmascarada en container logs
- ✅ No breaking change: default behavior unchanged
- ✅ 38 logger tests, 100% coverage
