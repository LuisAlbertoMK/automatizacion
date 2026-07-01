# P3: PLAN — agente-tramites-gobmx

**Date**: 2026-07-01
**Subagents**: 3 (I/R Scoring, Dependency Graph, Rollback Strategy)

---

## I/R Scoring Summary

| Batch | Descripción | I(1-5) | R(1-5) | I/R | Effort | Deps | Veredicto |
|-------|-------------|--------|--------|-----|--------|------|-----------|
| **A** | Security Quick Wins | 4 | 1 | **4.00** | S | None | **GO** |
| **B** | PII Sanitization | 5 | 2 | **2.50** | M | None | **GO** |
| **C** | API Security | 4 | 2 | **2.00** | M | None | **GO** |
| **E** | Fix Blocking Operations | 3 | 3 | **1.00** | M | None | **GO** |
| **F** | Dependency & Build Cleanup | 3 | 2 | **1.50** | M | None | **GO** |
| **G** | Docker Optimization | 3 | 2 | **1.50** | M | F (weak) | **GO** |
| **I** | Merge Buro/Circulo | 2 | 2 | **1.00** | M | None (decoupled) | **GO** |
| **J** | Add Tramite Module Tests | 4 | 1 | **4.00** | L | None | **GO** |
| **L** | Lazy Loading & Startup | 3 | 2 | **1.50** | M | None | **GO** |
| **D** | Browser Connection Pool | 3 | 4 | **0.75** | L | None | **SKIP** |
| **H** | Reduce Module Boilerplate | 2 | 4 | **0.50** | L | D | **SKIP** |
| **K** | Replace if/elif Chains | 2 | 3 | **0.67** | S | None | **SKIP** |
| **M** | Model Cleanup | 2 | 4 | **0.50** | M | None | **SKIP** |

**Total GO**: 9 batches · **SKIP**: 4 batches · **Gate**: ✅ ≥1 batch with I/R ≥ 1.0

---

## Dependency Graph

### Conflict Map (per file)

```
base.py:             A, E          → serial
nss.py:              B, E          → serial  
captcha.py:          E, L          → serial
orchestrator.py:     B, L          → serial
voice_input.py:      A, B          → serial
Dockerfile:          F, G          → serial
```

**Critical path** (longest chain): `A → E → B → L` (4 phases via base.py → nss.py → orchestrator.py)

### Independent Clusters
- **C** (api.py) — sin conflictos con nadie
- **J** (tests/) — archivos nuevos, sin conflictos  
- **I** (buro/circulo merge) — aislado si se separa de H

---

## Execution Phases

```
FASE 0 ─── PARALLELO ───────────────────────────────
  Track X: A (Security Quick Wins)     archivos: base.py, antecedentes.py, storage.py, voice_input.py
  Track Y: F (Dependencies)            archivos: pyproject.toml, requirements.txt, Dockerfile
  Track Z: C (API Security)            archivos: api.py (independiente)
             J (Tests)                 archivos: tests/ (nuevos, sin conflicto)
  → No overlap entre tracks

FASE 1 ─── PARALLELO ───────────────────────────────
  Track X: E (Fix Blocking Ops)        necesita: base.py ✅ (Fase 0)
  Track Y: G (Docker)                  necesita: Dockerfile ✅ (Fase 0)
  Track Z: L (Lazy Loading)            archivos: main.py, captcha.py, orchestrator.py

FASE 2 ─── PARALLELO ───────────────────────────────
  Track X: B (PII Sanitization)        necesita: nss.py ✅ (Fase 1)
  Track Y: I (Merge Buro/Circulo)      archivos: buro.py, circulo.py (aislado)

FASE 3 ─── (opcional) ──────────────────────────────
  - P5: VERIFY & LEARN con score final
```

---

## Rollback Strategy

### Per-Batch Rollback

| Batch | Método | Verification Gate | Recovery |
|-------|--------|-------------------|----------|
| **A** | `git revert` | ruff + pytest | ~5 min |
| **B** | `git revert` | pytest + profile load | ~10 min |
| **C** | `git revert` | pytest test_api.py | ~5 min |
| **E** | `git revert` | pytest test_base.py | ~10 min |
| **F** | `git revert` + pip reinstall | pip install + health_check | ~30 min |
| **G** | `git revert` | docker build | ~20 min |
| **I** | `git checkout <2 files>` | pytest + TRAMITES_REGISTRADOS | ~10 min |
| **J** | `git revert` | pytest | ~2 min |
| **L** | `git revert` | import speed + pytest | ~10 min |

### Pre-Batch Checklist
1. `git status --porcelain` → clean
2. Tag: `git tag pre-{BATCH}_$(date +%Y%m%d)`
3. `python -m pytest tests/ -v --tb=short` → all pass
4. `ruff check src/ tests/` → clean
5. Backup: `output/perfiles.json` → `output/perfiles.pre-{BATCH}.json`

### Global Revert Threshold
- Score drop ≥ **1.5 points** (de 7.0 → ≤ 5.5) → revertir todo
- Any single dimension drops below pre-audit level → revertir
- >3 critical tests failing → revertir inmediato

---

## Go Decision

✅ **Proceeding to P4: EXECUTE** with 9 GO batches in 3 fases.
Comenzando con **Fase 0**: A + F + C + J en paralelo.
