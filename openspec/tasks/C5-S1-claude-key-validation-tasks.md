# SDD Tasks: C5-S1 — Claude API Key Validation Hardening

**Spec**: C5-S1  
**Design**: C5-S1  

## Task 1: Add imports and constants to `src/utils/claude.py`
- [ ] Add `import re` to imports
- [ ] Add `_ANTHROPIC_KEY_PATTERN` constant (compiled regex)
- [ ] Add `_ANTHROPIC_KEY_MIN_LENGTH = 50`

## Task 2: Add `_validate_api_key()` function to `src/utils/claude.py`
- [ ] Implement function with 3 validation rules (empty, length, regex)
- [ ] Each failure raises `ClaudeError` with specific guidance message
- [ ] Place function between `_get_httpx_client()` and `call_claude()`

## Task 3: Update `call_claude()` in `src/utils/claude.py`
- [ ] Replace inline check with `_validate_api_key(api_key)` call

## Task 4: Update test fixture in `tests/test_claude.py`
- [ ] Change `ANTHROPIC_API_KEY` from `"sk-ant-test-key-12345"` to `"sk-ant-api-0P1xYz-test-abc123-456def789"`

## Task 5: Add new test cases in `tests/test_claude.py`
- [ ] `test_raises_on_key_too_short` — key with correct prefix but <50 chars
- [ ] `test_raises_on_wrong_prefix` — `sk-ant-` but not `sk-ant-api-`
- [ ] `test_valid_key_passes_validation` — realistic key passes validation (mocked 200 response)

## Task 6: Verify
- [ ] Run `pytest tests/test_claude.py -v` — all pass
- [ ] Run `ruff check src/utils/claude.py tests/test_claude.py` — clean
- [ ] Run `pytest --cov-fail-under=80` — passes
- [ ] Verify claude.py coverage ≥ 95%
