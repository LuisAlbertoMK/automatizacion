# SDD Proposal: COMP-1 — Refactor modo_interactivo Complexity

**ID**: COMP-1-S1  
**Date**: 2026-08-26  
**Status**: PROPOSED  
**Gap from**: analysis v2, item COMP-1 (ICE 2.0)

## Intent

Reduce cyclomatic complexity E(32) of `modo_interactivo()` in `src/main.py` by extracting command dispatch into a dictionary-based lookup table and separate functions for document generation and natural language processing. Target: E < 15 for the main function.

## Context

- `src/main.py:502` `modo_interactivo()` — 79 lines with 20+ if/elif branches
- Complexity E(32) is critically high (threshold: E≤10 per function)
- 14 tests in `test_main.py::TestModoInteractivo` cover command dispatch, NLP, error handling
- Behavior must be preserved exactly (tests must pass without modification)

## Scope

### In
- `src/main.py` — Add `_TRAMITE_COMANDOS` dict, `_procesar_nlp()`, `_procesar_comando()` functions; refactor `modo_interactivo()` to use them
- `openspec/` — SDD artifacts (proposal, spec, design, tasks, archive)

### Out
- No changes to `Agente` class
- No changes to `modo_directo()` or other functions
- Tests unchanged (behavioral equivalence)
