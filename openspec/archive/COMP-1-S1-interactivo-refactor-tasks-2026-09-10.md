# SDD Tasks: COMP-1-S1 — Refactor modo_interactivo

## Task 1: Add command dispatch infrastructure to main.py
- [ ] Add `_TRAMITE_COMANDOS`, `_SALIR_COMANDOS`, `_AYUDA_COMANDOS`, `_DOCUMENTO_COMANDOS` constants
- [ ] Place before modo_interactivo, after Agente class

## Task 2: Extract `_generar_documento()` + helpers
- [ ] `_generar_documento(cmd)` → dispatches to cv/escrito
- [ ] `_generar_cv()` — DOCUMENTOS_AVAILABLE check + CVGenerator
- [ ] `_generar_escrito()` — same for EscritoGenerator

## Task 3: Extract `_procesar_nlp()`
- [ ] Keyword-based NLP dispatch (curp+nss → ambos, curp → curp, nss/seguro/imss → nss)

## Task 4: Extract `_procesar_comando()`
- [ ] Dict-based dispatch returning bool (False=exit, True=continue)
- [ ] Handles exit, help, tramite, documento, falls through to NLP

## Task 5: Refactor `modo_interactivo()`
- [ ] Replace if/elif chain with `_procesar_comando()` call
- [ ] Keep perfil special-case inline (modifies perfil_activo)
- [ ] Keep try/except, while loop, empty-input check

## Task 6: Verify
- [ ] pytest tests/test_main.py::TestModoInteractivo -v — all 14 pass
- [ ] ruff check src/main.py
- [ ] Verify behavior identical (same output, same method calls)
