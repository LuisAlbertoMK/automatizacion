# SDD Design: COMP-1-S1 — Refactor modo_interactivo

## Architecture Decision

**Pattern**: Command dispatch table (dictionary-based) + extracted helper functions  
**Principle**: Replace 20+ if/elif branches with dict lookup; extract NLP + documento logic to separate functions.

## Implementation Design

### 1. Command dispatch table

```python
_TRAMITE_COMANDOS = {
    "curp": "tramite_curp",
    "nss": "tramite_nss",
    "rfc": "tramite_rfc",
    "acta": "tramite_acta",
    "pasaporte": "tramite_pasaporte",
    "semanas": "tramite_semanas",
    "control_confianza": "tramite_control_confianza",
    "control": "tramite_control_confianza",
    "confianza": "tramite_control_confianza",
    "buro": "tramite_buro",
    "buro_credito": "tramite_buro",
    "circulo": "tramite_circulo",
    "circulo_credito": "tramite_circulo",
    "cita_ine": "tramite_cita_ine",
    "ine": "tramite_cita_ine",
    "cita_sat": "tramite_cita_sat",
    "sat": "tramite_cita_sat",
    "ambos": "tramite_ambos",
    "todo": "tramite_ambos",
    "nss+curp": "tramite_ambos",
    "curp+nss": "tramite_ambos",
}

_SALIR_COMANDOS = {"salir", "exit", "q"}
_AYUDA_COMANDOS = {"ayuda", "help", "?"}
_DOCUMENTO_COMANDOS = {"cv", "curriculum", "escrito", "carta", "documento"}
```

### 2. Extracted functions

```python
async def _generar_documento(cmd: str) -> None:
    """Genera CV o escrito según comando."""
    if cmd in ("cv", "curriculum"):
        _generar_cv()
    else:
        _generar_escrito()

def _generar_cv() -> None:
    if DOCUMENTOS_AVAILABLE:
        gen = CVGenerator()
        gen.generar_interactivo()
    else:
        print("  python-docx no instalado. Ejecutá: pip install python-docx")

def _generar_escrito() -> None:
    if DOCUMENTOS_AVAILABLE:
        gen = EscritoGenerator()
        gen.generar_interactivo()
    else:
        print("  python-docx no instalado. Ejecutá: pip install python-docx")

async def _procesar_nlp(cmd: str, agente, perfil) -> None:
    """Interpretar lenguaje natural para resolver trámites."""
    if "curp" in cmd and "nss" in cmd:
        await agente.tramite_ambos(perfil=perfil)
    elif "curp" in cmd:
        await agente.tramite_curp(perfil=perfil)
    elif "nss" in cmd or "seguro" in cmd or "imss" in cmd:
        await agente.tramite_nss(perfil=perfil)
    else:
        print(f"  Comando '{cmd}' no reconocido. Escribe 'ayuda'.")

async def _procesar_comando(cmd: str, agente, perfil) -> bool:
    """Procesa un comando. Retorna False para salir, True para continuar."""
    if cmd in _SALIR_COMANDOS:
        print("  Hasta luego.")
        return False
    if cmd in _AYUDA_COMANDOS:
        print(AYUDA)
        return True
    metodo = _TRAMITE_COMANDOS.get(cmd)
    if metodo:
        handler = getattr(agente, metodo, None)
        if handler:
            await handler(perfil=perfil)
        return True
    if cmd in _DOCUMENTO_COMANDOS:
        await _generar_documento(cmd)
        return True
    await _procesar_nlp(cmd, agente, perfil)
    return True
```

### 3. Refactored modo_interactivo

```python
async def modo_interactivo():
    """Modo interactivo REPL — bucle de comandos."""
    agente = Agente()
    print(BANNER)
    print(AYUDA)

    perfil_activo = None
    perfiles = list_profiles()
    if perfiles:
        print(f"  {Fore.CYAN}Perfiles guardados: {', '.join(perfiles)}{Style.RESET_ALL}")
        print()

    while True:
        try:
            cmd = input(f"{Fore.CYAN}tramites>{Style.RESET_ALL} ").strip().lower()
            if not cmd:
                continue
            if cmd == "perfil":
                p = agente.gestionar_perfil()
                if p:
                    perfil_activo = p
                    print(f"  {Fore.GREEN}Perfil cargado [OK]{Style.RESET_ALL}")
                continue
            if not await _procesar_comando(cmd, agente, perfil_activo):
                break
        except KeyboardInterrupt:
            print("\n  Interrumpido. Escribe 'salir' para salir.")
        except Exception as e:
            print(f"  {Fore.RED}Error: {e}{Style.RESET_ALL}")
```

## Complexity Analysis

| Function | Before E | After E |
|----------|----------|---------|
| modo_interactivo | 32 | ~8 |
| _procesar_comando | 0 | ~7 |
| _procesar_nlp | 0 | ~5 |
| _generar_documento | 0 | ~3 |

## Placement
Place dispatch table + helpers BEFORE `modo_interactivo` (after `Agente` class).

## Behavioral Equivalence
- All command mappings identical to original elif chain
- Error handling (KeyboardInterrupt, Exception) preserved in loop
- `perfil` command handled specially (modifies perfil_activo) — same as original
- `not cmd: continue` preserved
- Empty/None results for documento commands: same print messages
