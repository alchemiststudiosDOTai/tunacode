---
title: Utils Limits
path: src/tunacode/utils/limits.py
type: file
depth: 1
description: Centralized tool output limits with cascading defaults
exports: [is_local_mode, get_read_limit, get_max_line_length, get_command_limit, get_max_files_in_dir, get_max_tokens, clear_cache]
seams: [M]
---

# Utils Limits

## Purpose

Centralizes all tool output limit configuration with a three-tier precedence system. Acts as the **central control point** for local mode - a single `is_local_mode()` check cascades through 6 optimization layers across the system.

## The 6 Optimization Layers

When `local_mode: true`, these layers are activated:

| Layer | Component | Effect |
|-------|-----------|--------|
| 1 | System prompt | LOCAL_TEMPLATE (3 sections) vs MAIN_TEMPLATE (11 sections) |
| 2 | Guide file | `local_prompt.md` (~500 tok) vs user's AGENTS.md |
| 3 | Tool set | 6 tools with 1-word descriptions vs 11 tools |
| 4 | Output limits | 10x smaller limits (this module) |
| 5 | Response cap | 1000 tokens vs unlimited |
| 6 | Pruning | 20x more aggressive (2k vs 40k protection) |

## Precedence System

```
explicit setting > local_mode default > standard default
```

Implemented in `_get_limit()` at lines 42-56:

```python
def _get_limit(key: str, default: int, local_default: int) -> int:
    settings = _load_settings()

    # Explicit setting wins
    if key in settings:
        return settings[key]

    # Otherwise use mode-appropriate default
    if settings.get("local_mode", False):
        return local_default
    return default
```

## Key Functions

### is_local_mode() (line 59-61)

Central mode detection. Returns `True` if `settings.local_mode` is enabled.

```python
def is_local_mode() -> bool:
    return _load_settings().get("local_mode", False)
```

### get_read_limit() (line 64-66)

Max lines returned by `read_file`.
- Standard: 2000 lines
- Local: 200 lines

### get_max_line_length() (line 69-71)

Truncate lines longer than this.
- Standard: 2000 chars
- Local: 500 chars

### get_command_limit() (line 74-76)

Max chars from `bash` output.
- Standard: 5000 chars
- Local: 1500 chars

### get_max_files_in_dir() (line 79-81)

Max entries from `list_dir`.
- Standard: 50 files
- Local: 20 files

### get_max_tokens() (line 84-96)

Cap on model response length.
- Explicit `max_tokens` setting takes precedence
- Local mode: uses `local_max_tokens` (default: 1000)
- Standard mode: returns `None` (unlimited)

### clear_cache() (line 99-101)

Clears the `@lru_cache` on settings. Call when config changes at runtime.

## Limit Comparison Table

| Setting | Standard | Local | Reduction |
|---------|----------|-------|-----------|
| `read_limit` | 2000 | 200 | 10x |
| `max_line_length` | 2000 | 500 | 4x |
| `max_command_output` | 5000 | 1500 | 3.3x |
| `max_files_in_dir` | 50 | 20 | 2.5x |
| `max_tokens` | unlimited | 1000 | capped |

## Configuration Examples

**Pure local mode** - all aggressive defaults:
```json
{"settings": {"local_mode": true}}
```

**Local mode with custom override**:
```json
{"settings": {"local_mode": true, "read_limit": 500}}
```
Result: Uses 500 (explicit wins over local default of 200).

**Standard mode with selective limits**:
```json
{"settings": {"local_mode": false, "max_command_output": 2000}}
```
Result: Standard mode but with reduced command output.

## Integration Points

| Consumer | File | Usage |
|----------|------|-------|
| Bash tool | `tools/bash.py` | `get_command_limit()` |
| Read tool | `tools/read_file.py` | `get_read_limit()`, `get_max_line_length()` |
| List dir tool | `tools/list_dir.py` | `get_max_files_in_dir()` |
| Compaction | `core/compaction.py` | `is_local_mode()` for prune thresholds |
| Agent config | `core/agents/agent_config.py` | `is_local_mode()`, `get_max_tokens()` |
| System prompt | `core/agents/agent_config.py` | `is_local_mode()` for template selection |
| Tool selection | `core/agents/agent_config.py` | `is_local_mode()` for minimal tool set |

## Design Notes

- **Caching**: Uses `@lru_cache(maxsize=1)` for settings load
- **Circular import avoidance**: Imports config loader inside function
- **Binary switch**: Local mode is on/off, not graduated
- **Prune thresholds**: Stay in `compaction.py` (not user-configurable)

## Constants Location

Default values defined in `constants.py`:

```python
# Standard defaults (lines 24-27)
DEFAULT_READ_LIMIT = 2000
DEFAULT_MAX_LINE_LENGTH = 2000
DEFAULT_MAX_COMMAND_OUTPUT = 5000
DEFAULT_MAX_FILES_IN_DIR = 50

# Local mode defaults (lines 29-34)
LOCAL_READ_LIMIT = 200
LOCAL_MAX_LINE_LENGTH = 500
LOCAL_MAX_COMMAND_OUTPUT = 1500
LOCAL_MAX_FILES_IN_DIR = 20
LOCAL_MAX_TOKENS = 1000
```

## Seams (M)

**Modification Points:**
- Add new limit types (follow `_get_limit()` pattern)
- Change default values in `constants.py`
- Add new mode-specific behaviors
- Extend precedence logic
