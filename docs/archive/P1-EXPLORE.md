# P1: EXPLORE — agente-tramites-gobmx

**Date**: 2026-07-01
**Project**: agente-tramites-gobmx v1.0.0 (score 7.0 ↑)
**Subagents**: 3 (Structure, Architecture, Dependencies)

---

## Structure Summary

- **Root shims**: `app.py` (Streamlit), `main.py` / `main_multimodal.py` (CLI) — thin shims that add `src/` to path
- **Canonical source**: `src/` directory
  - `src/main.py` — `Agente` class (CLI interactive REPL)
  - `src/main_multimodal.py` — `TramitesOrchestrator` (multimodal routing)
  - `src/api.py` — FastAPI REST API
  - `src/modules/` — 15 tramite modules + `base.py` (Template Method) + `orchestrator.py`
  - `src/utils/` — 9 utility modules (captcha, OCR, storage, logger, IMAP, Claude, voice, multimodal)
- **Tests**: 12 pytest files in `tests/` + 12 integration test scripts at root
- **LoC**: ~85 Python files across the codebase
- **13 modules** per government procedure, 2 document generators (CV, Escrito)
- **IMSS CAPTCHA solver**: standalone project (`captcha_solver_imss/`) with CNN + EasyOCR + Tesseract ensemble

## Architecture Findings

### Strengths
- **Template Method** via `BaseModule` → consistent lifecycle across all modules
- **Strategy** pattern for CAPTCHA solving: 2captcha → FreeCaptcha → CNN → manual
- **Facade**: `MultimodalInput` unifies text/voice/image input
- **Graceful degradation**: fallback chains for captcha, OCR, email extraction
- **Rate limiting**: module-level `REQUEST_DELAY` prevents portal blocking
- **Exception hierarchy**: `TramiteError` → `CaptchaError`, `ModuleError`, `StorageError`, etc.

### Weaknesses
- **Code duplication**: `Agente` class (src/main.py) and `TramitesOrchestrator` (src/modules/orchestrator.py) duplicate tramite methods
- **God class**: `BaseModule` (~414 lines) mixes browser lifecycle, CAPTCHA, PDF, logging, HTML parsing — violates SRP
- **Global mutable state**: `_last_request_time` module variable in `base.py` — not thread-safe
- **`except Exception: pass`** throughout — swallows errors, hinders debugging
- **Mixed sync/async**: 2captcha sync methods called via `run_in_executor`
- **No circuit breaker** for external services (2captcha, IMAP, Claude API)

## Dependencies Findings

### Critical Undeclared Dependencies
| Package | Used In | Missing From |
|---------|---------|-------------|
| **torch** | captcha_solver_imss/ | requirements.txt, pyproject.toml |
| **opencv-python** | captcha_solver_imss/ | requirements.txt, pyproject.toml |
| **easyocr** | captcha_solver_imss/ | requirements.txt, pyproject.toml |
| **python-docx** | src/modules/documentos/ | requirements.txt, pyproject.toml |
| **onnxruntime** | captcha_solver_imss/ | requirements.txt, pyproject.toml |

### Other Risks
- **No lock file** — builds are non-reproducible
- **11 PyTorch models (~112 MB)** gitignored — missing in fresh CI/Docker builds
- **Dockerfile installs only base requirements** — FastAPI/Streamlit not included in image
- **Tesseract paths hardcoded** for Windows — fragile on Linux

### Infrastructure
- **Docker Compose** with 3 services: CLI, Streamlit (app), FastAPI (api)
- **GitHub Actions CI**: ruff linting + pytest with matrix (3.11/3.12/3.13) + Docker build
- **No deployment** configured (no registry push)
- **No database** — all state is file-based (encrypted JSON, JSONL metrics)

---

## Gate: All 3 reports complete ✅ → Proceeding to P2
