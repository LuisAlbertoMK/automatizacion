# SDD Archive: C5-S1 — Claude API Key Validation Hardening

**Status**: COMPLETED  
**Commit**: `4141a92`  
**Date**: 2026-08-26  

## Results

| Metric | Target | Actual |
|--------|--------|--------|
| Tests | All pass | **18/18 passed** ✅ |
| claude.py coverage | ≥ 80% | **100%** (51 stmts, 0 miss) ✅ |
| ruff | Clean | **All checks passed** ✅ |
| Breaking changes | None | `call_claude()` signature unchanged ✅ |

## Delta Summary

### Added
- `_validate_api_key(api_key: str) -> None` — 3-rule validation
- `_ANTHROPIC_KEY_PATTERN` — regex `^sk-ant-api-[A-Za-z0-9_-]{10,}$`
- `_ANTHROPIC_KEY_MIN_LENGTH = 50`
- 6 unit tests in `TestValidateApiKey` class
- 3 integration tests for `call_claude()` validation paths

### Modified
- `call_claude()` — replaced inline `startswith("sk-ant-")` with `_validate_api_key()` call
- Test fixture — updated to realistic key format `sk-ant-api-0P1xYz-test-abc123-456def78901234567890`

### Removed
- `test_raises_on_invalid_api_key_prefix` — replaced by `test_raises_on_wrong_prefix` (more precise)

## Artifacts
- Proposal: `openspec/proposals/C5-claude-key-validation.md`
- Spec: `openspec/specs/C5-S1-claude-key-validation-spec.md`
- Design: `openspec/designs/C5-S1-claude-key-validation-design.md`
- Tasks: `openspec/tasks/C5-S1-claude-key-validation-tasks.md`
- Code: `src/utils/claude.py`, `tests/test_claude.py`

## Lessons
- `sk-ant-old-...` keys (≥50 chars, correct old prefix) pass length but fail regex → format error
- `sk-ant-test-key-12345` (~19 chars) fails length check before regex — order matters in test key construction
- `.atl/` directory is gitignored (auto-generated); skill-registry update was not committed
