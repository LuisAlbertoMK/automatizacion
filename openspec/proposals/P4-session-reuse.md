# SDD Proposal: P4 — requests.Session Reuse via http_client Module

**ID**: P4-S1  
**Date**: 2026-08-26  
**Status**: PROPOSED  

## Intent

Replace 10 direct `requests.get/post(...)` call sites across 5 source files with a shared
`requests.Session` singleton that provides connection pooling, retry strategy, and centralized
HTTP configuration. This eliminates per-call connection overhead and enables TCP connection reuse.

## Context (from analysis v2)

- **Gap P4** (ICE 2.0): 8 call sites use `requests.get/post` directly (analysis counted 8; explore found 10)
- No connection pooling — each call opens a new TCP connection
- No centralized retry strategy for HTTP 5xx errors
- 5 different `User-Agent` / timeout patterns scattered across modules

## Scope

### In
- **NEW**: `src/utils/http_client.py` — `get_http_session()` singleton + `close_http_session()`
- `src/utils/captcha.py` — 5 sync + 4 async call sites
- `src/tramites/base.py` — 1 call site (run_in_executor)
- `src/tramites/nss.py` — 1 call site (run_in_executor)
- `src/tramites/cedula_profesional.py` — 1 call site (run_in_executor)
- `src/tramites/acta_nacimiento.py` — 1 call site (asyncio.to_thread) + remove local `import requests`

### Tests
- `tests/test_captcha.py` — update ~30 patches
- `tests/test_nss.py` — update ~10 patches
- `tests/test_cedula_profesional.py` — update ~4 patches
- `tests/test_base.py` — update ~5 patches
- `tests/test_acta_nacimiento.py` — update ~2 patches

### Out
- No changes to FastAPI API layer (api.py uses httpx, not requests)
- No changes to free_captcha.py (it patches `requests.get` globally — separate concern)
