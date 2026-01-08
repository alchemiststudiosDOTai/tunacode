---
title: Core Limits
path: src/tunacode/core/limits.py
type: file
depth: 1
description: Centralized tool output limits with cascading defaults
exports: [is_local_mode, get_read_limit, get_max_line_length, get_command_limit, get_max_files_in_dir, get_max_tokens, clear_cache]
seams: [M]
---

# Core Limits

## Purpose

Centralizes all tool output limit configuration with a three-tier precedence system:
1. Explicit user setting
2. local_mode default
3. Standard default

## Key Functions

### is_local_mode()
Returns `True` if `settings.local_mode` is enabled.

### get_read_limit()
Max lines returned by `read_file`. Default: 2000, local: 200.

### get_max_line_length()
Truncate lines longer than this. Default: 2000, local: 500.

### get_command_limit()
Max chars from `bash` output. Default: 5000, local: 1500.

### get_max_files_in_dir()
Max entries from `list_dir`. Default: 50, local: 20.

### get_max_tokens()
Cap on model response length. Returns `None` if unlimited.
- Explicit `max_tokens` setting takes precedence
- local_mode uses `local_max_tokens` (default: 1000)
- Standard mode: unlimited

### clear_cache()
Clears the settings cache. Call when config changes at runtime.

## Precedence

```
explicit setting > local_mode default > standard default
```

Example:
```json
{"settings": {"local_mode": true, "read_limit": 500}}
```
Uses 500 (explicit wins over local_mode default of 200).

## Integration Points

- **tools/bash.py** - Uses `get_command_limit()`
- **tools/read_file.py** - Uses `get_read_limit()`, `get_max_line_length()`
- **tools/list_dir.py** - Uses `get_max_files_in_dir()`
- **core/compaction.py** - Uses `is_local_mode()` for prune thresholds
- **core/agents/agent_config.py** - Uses `is_local_mode()`, `get_max_tokens()`

## Design Notes

- Uses `@lru_cache` for settings load (call `clear_cache()` if config changes)
- Import inside function to avoid circular imports
- Prune thresholds stay in `compaction.py` (binary switch, not user-configurable)

## Seams (M)

**Modification Points:**
- Add new limit types
- Change default values in `constants.py`
- Adjust local_mode defaults
