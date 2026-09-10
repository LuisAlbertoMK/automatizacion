# SDD Spec: COMP-1-S1 — Refactor modo_interactivo

**Proposal**: COMP-1-S1

## Requirements

### REQ-1: Command dispatch table
Add `_TRAMITE_COMANDOS` dict mapping command strings → agent method names (same 21 mappings as original elif chain).

### REQ-2: Exit/help command sets
Add `_SALIR_COMANDOS = {"salir", "exit", "q"}` and `_AYUDA_COMANDOS = {"ayuda", "help", "?"}`.

### REQ-3: Extract NLP handler
Add `_procesar_nlp(cmd, agente, perfil)` function handling keyword-based dispatch (curp+nss → ambos, curp → curp, nss/seguro/imss → nss, else → not found).

### REQ-4: Extract document handler  
Add `_generar_documento(cmd)` function for cv/escrito commands with DOCUMENTOS_AVAILABLE check.

### REQ-5: Extract command processor
Add `_procesar_comando(cmd, agente, perfil) -> bool` returning False to signal exit.

### REQ-6: Refactor modo_interactivo
Main function should be under E(15) — just the loop, input handling, special perfil case, and try/except.

### REQ-7: Behavioral equivalence
All 14 existing tests must pass without modification.

## Scenarios

### Scenario: Command dispatch — "curp"
```
Given cmd="curp" and mock_agente with tramite_curp=AsyncMock()
When _procesar_comando("curp", agente, None) is called
Then agente.tramite_curp.assert_awaited_once()
And returns True
```

### Scenario: Exit command — "salir"
```
Given cmd="salir"
When _procesar_comando("salir", agente, None) is called
Then prints "Hasta luego."
And returns False
```

### Scenario: NLP fallback — "quiero curp y nss"
```
Given cmd="quiero curp y nss" and mock_agente with tramite_ambos=AsyncMock()
When _procesar_comando("quiero curp y nss", agente, None) is called
Then agente.tramite_ambos.assert_awaited_once()
```

### Scenario: Unknown command
```
Given cmd="xyz123"
When _procesar_comando("xyz123", agente, None) is called
Then prints "no reconocido"
```

### Scenario: Perfil command (special)
```
Given cmd="perfil" and agente.gestionar_perfil returns {"curp": "XXX"}
When processed in modo_interactivo loop
Then perfil_activo is set to the returned profile
And "Perfil cargado" is printed
```

## Test Plan

| Test | Status |
|------|--------|
| test_curp_command | Existing — must pass |
| test_nss_command | Existing — must pass |
| test_ambos_command | Existing — must pass |
| test_comando_dispatch (17 params) | Existing — must pass |
| test_ayuda_command | Existing — must pass |
| test_natural_language_curp_nss | Existing — must pass |
| test_natural_language_curp_only | Existing — must pass |
| test_natural_language_nss | Existing — must pass |
| test_exit_command | Existing — must pass |
| test_unknown_command | Existing — must pass |
| test_keyboard_interrupt | Existing — must pass |
| test_perfil_command_loads_profile | Existing — must pass |
| test_exception_during_command | Existing — must pass |
| test_empty_line_skips | Existing — must pass |

## Non-Goals
- No new features
- No changes to modo_directo
- No changes to test_main.py
