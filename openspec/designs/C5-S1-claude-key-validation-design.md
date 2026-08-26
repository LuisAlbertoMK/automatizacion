# SDD Design: C5-S1 — Claude API Key Validation Hardening

## Architecture Decision

**Pattern**: Guard clause / Validation function  
**Approach**: Extract inline validation into a dedicated `_validate_api_key()` function for testability and clarity.  
**Rationale**: Single responsibility — validation logic separated from HTTP logic. Enables independent unit testing without mocking httpx.

## Implementation Design

### 1. New function: `_validate_api_key`

```python
import re

# Anthropic API key format: sk-ant-api-<alphanumeric-segments>
_ANTHROPIC_KEY_PATTERN = re.compile(r"^sk-ant-api-[A-Za-z0-9_-]{10,}$")
_ANTHROPIC_KEY_MIN_LENGTH = 50

def _validate_api_key(api_key: str) -> None:
    """
    Validates that the provided API key matches Anthropic's format.

    Raises:
        ClaudeError: If the key is empty, too short, or has wrong format.
    """
    if not api_key:
        raise ClaudeError(
            "ANTHROPIC_API_KEY no configurada o inválida.\n"
            "  1. Configurá ANTHROPIC_API_KEY en config.env o Windows Credential Manager\n"
            "  2. Obtené tu API key en https://console.anthropic.com"
        )
    if len(api_key) < _ANTHROPIC_KEY_MIN_LENGTH:
        raise ClaudeError(
            "ANTHROPIC_API_KEY es demasiado corta (mínimo 50 caracteres).\n"
            "  1. Configurá ANTHROPIC_API_KEY en config.env o Windows Credential Manager\n"
            "  2. Obtené tu API key en https://console.anthropic.com"
        )
    if not _ANTHROPIC_KEY_PATTERN.match(api_key):
        raise ClaudeError(
            "ANTHROPIC_API_KEY inválida — formato incorrecto.\n"
            "  1. La clave debe comenzar con 'sk-ant-api-'\n"
            "  2. Obtené tu API key en https://console.anthropic.com"
        )
```

### 2. Updated `call_claude()` entry point

```python
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    _validate_api_key(api_key)
    # ... rest of function unchanged ...
```

### 3. Import additions

Add `import re` at top of `claude.py`.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Regex vs exact format | Regex with min length | Anthropic key segments vary; regex + length is robust without being brittle |
| Min length | 50 chars | Real keys are 100+; 50 catches truncation without false rejection |
| Error messages | Specific per failure type | Clear guidance for user to diagnose: empty, too short, wrong format |
| Private function | `_validate_api_key` | Not part of public API; tested via `call_claude()` + direct unit tests |
| No network check | Offline only | Avoids adding latency/dependency; API error handling already exists |

## Non-Goals

- No API call to verify key validity (would add network dependency + latency).
- No key caching (keys don't change within a process typically; env var read is O(1)).
- No integration with Windows Credential Manager (already documented as alternative in error message).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| False rejection of valid keys | Low | Medium | Regex is permissive (`[A-Za-z0-9_-]`); min length 50 well below real keys |
| Existing test breakage | High | Low | Fixture updated to realistic format; all 7 existing tests adapted |
| Breaking API callers | None | Low | `call_claude()` signature unchanged; behavior is superset (more validation) |
