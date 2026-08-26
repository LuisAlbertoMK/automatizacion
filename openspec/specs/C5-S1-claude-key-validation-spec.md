# SDD Spec: C5-S1 — Claude API Key Validation Hardening

**Proposal**: C5-S1  
**Spec version**: 1.0  
**Files changed**: `src/utils/claude.py`, `tests/test_claude.py`  

## Requirements

### REQ-1: Structured key validation function
- **Description**: Add `_validate_api_key(api_key: str) -> None` that validates the Anthropic API key format.
- **Behavior**: Raises `ClaudeError` if invalid; returns `None` if valid.

### REQ-2: Replace inline prefix check
- **Description**: In `call_claude()`, replace `if not api_key or not api_key.startswith("sk-ant-"):` with a call to `_validate_api_key(api_key)`.

### REQ-3: Validation rules
1. Key must not be empty or `None`.
2. Key must start with `sk-ant-api-`.
3. Key must be at least 50 characters total.
4. After the `sk-ant-api-` prefix, there must be at least 10 alphanumeric characters.

### REQ-4: Preserve actionable error message
- The ClaudeError raised must include the same guidance text: config.env / Credential Manager / console link instructions.

### REQ-5: Test fixture aligned to real format
- Update test fixture key from `"sk-ant-test-key-12345"` to a realistic key: `"sk-ant-api-0P1xYz-test-abc123-456def789"`.

### REQ-6: New test cases
- `test_raises_on_key_too_short`: Key with correct prefix but <50 chars → ClaudeError.
- `test_raises_on_wrong_prefix`: Key starting with `sk-ant-` but not `sk-ant-api-` → ClaudeError.
- `test_valid_key_passes_validation`: Realistic key → no ClaudeError at validation stage (mocked API returns 200).

## Scenarios

### Scenario: Valid key — passes validation, API returns 200
```
Given ANTHROPIC_API_KEY = "sk-ant-api-0P1xYz-test-abc123-456def78901234567890"
When call_claude([{"role": "user", "content": "test"}]) is called
And the mocked API returns 200 with valid content
Then _validate_api_key does not raise
And call_claude returns the parsed JSON result
```

### Scenario: Key too short — validation fails
```
Given ANTHROPIC_API_KEY = "sk-ant-api-short"
When call_claude([{"role": "user", "content": "test"}]) is called
Then ClaudeError is raised with message containing "inválida"
And no HTTP request is made
```

### Scenario: Wrong prefix — validation fails
```
Given ANTHROPIC_API_KEY = "sk-ant-test-key-1234567890123456789012345678901234567890123456789012"
When call_claude([]) is called
Then ClaudeError is raised with message containing "inválida"
And no HTTP request is made
```

### Scenario: Empty key — validation fails
```
Given ANTHROPIC_API_KEY is not set
When call_claude([]) is called
Then ClaudeError is raised with message containing "ANTHROPIC_API_KEY no configurada"
And no HTTP request is made
```

## Test Plan

| Test | File | Expected |
|------|------|----------|
| `test_raises_on_missing_api_key` | test_claude.py | ClaudeError (existing, passes with no key) |
| `test_raises_on_key_too_short` | test_claude.py | ClaudeError (NEW) |
| `test_raises_on_wrong_prefix` | test_claude.py | ClaudeError (NEW — rename from old prefix test) |
| `test_valid_key_passes_validation` | test_claude.py | JSON result returned (NEW) |
| `test_returns_parsed_json` | test_claude.py | JSON result (existing, needs fixture update) |
| `test_passes_correct_payload` | test_claude.py | Correct URL/headers (existing, needs fixture update) |
| `test_strips_markdown_backticks` | test_claude.py | Clean JSON (existing, needs fixture update) |
| All timeout/connection/error tests | test_claude.py | ClaudeError (existing, needs fixture update) |

## Coverage Impact
- `_validate_api_key()` will be fully covered by new tests.
- `call_claude()` validation branch fully covered.
- Target: claude.py lines covered ≥ 95%.
