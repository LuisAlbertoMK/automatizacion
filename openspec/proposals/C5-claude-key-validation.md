# SDD Proposal: C5 — Claude API Key Validation Hardening

**ID**: C5-S1  
**Date**: 2026-08-26  
**Author**: Orchestrator (sdd-init-2026-08-26)  
**Status**: PROPOSED  

## Intent

Improve the security and reliability of the `ANTHROPIC_API_KEY` validation in `src/utils/claude.py` by replacing the weak prefix-only check (`startswith("sk-ant-")`) with a structured format+length validation. This prevents misconfiguration with malformed keys that would only fail at API-call time, producing confusing errors.

## Context (from analysis v2)

- **Gap C5** (ICE 1.5): `claude.py:55` validates key only by prefix `sk-ant-`.
- Any string starting with `sk-art-` passes — e.g., `"sk-ant-"`, `"sk-ant-x"`, `"sk-ant-bogus"` — all pass validation, failing later at the API call with a vague 401.
- Real Anthropic keys follow format: `sk-ant-api-<segment>-<segment>-...` with total length ~100+ chars.

## Scope

### In
- `src/utils/claude.py` — Add `_validate_api_key()` function; update `call_claude()` to call it.
- `tests/test_claude.py` — Add test cases for new validation; update fixture key to realistic format.

### Out
- No changes to API call logic, error response handling, or JSON parsing.
- No network calls added (validation is offline).
- `src/exceptions.py` — `ClaudeError` already exists; no changes needed.

## Approach

1. **Add regex-based key validation** (`_validate_api_key`):
   - Must match `^sk-ant-api-` prefix (Anthropic's actual format).
   - Must have minimum total length (e.g., 50 chars).
   - Must contain at least one alphanumeric segment after prefix.
2. **Update `call_claude()`**: Replace inline `if not api_key or not api_key.startswith("sk-ant-"):` with a call to `_validate_api_key()`.
3. **Keep error message actionable**: Same guidance text (config.env / Credential Manager / console link).
4. **Update test fixture**: Change `"sk-ant-test-key-12345"` to a realistic format `"sk-ant-api-0P1xYz-test-abc123-456def789"` so existing tests remain valid.
5. **Add test cases**:
   - Key with correct prefix but too short → ClaudeError
   - Key with correct format → passes validation (no early error)
   - Empty key → ClaudeError (already tested)
   - Key with old `sk-ant-` but not `sk-ant-api-` → ClaudeError

## Assumptions

- Anthropic keys always start with `sk-ant-api-0P` followed by segments. (Verified: public docs show format `sk-ant-api-<uuid-segments>`.)
- No performance concern (single regex check at call start).
- No breaking change to existing callers — `call_claude()` signature unchanged.

## Success Criteria

- ✅ `_validate_api_key()` function exists and is unit-testable independently.
- ✅ All existing tests pass with updated fixture.
- ✅ New tests cover: short key, wrong prefix, correct format.
- ✅ `pytest --cov-fail-under=80` passes (claude.py stays at or above threshold).
- ✅ ruff lint clean (`ruff check src/utils/claude.py tests/test_claude.py`).
