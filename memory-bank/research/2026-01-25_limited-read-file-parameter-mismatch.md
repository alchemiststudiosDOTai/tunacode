# Research – limited_read_file Parameter Mismatch Bug

**Date:** 2026-01-25
**Owner:** Claude
**Phase:** Fixed

## Goal

Diagnose and fix `TypeError: 'NoneType' object is not subscriptable` and `limited_read_file() missing 1 required positional argument: 'filepath'` errors occurring in the research agent.

## Findings

### Error Manifestation

```
TypeError: _create_limited_read_file.<locals>.limited_read_file() missing 1 required positional argument: 'filepath'
```

The error occurs when pydantic-ai attempts to invoke the `limited_read_file` tool during research agent execution.

### Relevant Files

| File | Relevance |
|------|-----------|
| `src/tunacode/core/agents/research_agent.py:77` | Defines `limited_read_file` with parameter `file_path` |
| `src/tunacode/tools/decorators.py:183` | `@file_tool` wrapper hardcodes parameter name `filepath` |

### Root Cause

**Parameter name mismatch** between the `@file_tool` decorator and `limited_read_file`:

1. The `@file_tool` decorator creates a wrapper function with a **hardcoded** parameter name:
   ```python
   async def wrapper(filepath: str, *args: Any, **kwargs: Any) -> str:
   ```

2. The decorator preserves the original function's signature for pydantic-ai schema generation:
   ```python
   wrapper.__signature__ = inspect.signature(fn)  # Shows "file_path"
   ```

3. When pydantic-ai calls the tool, it reads the signature and passes `file_path='...'` as a keyword argument.

4. The wrapper expects `filepath` (no underscore), so `file_path` falls into `**kwargs` instead of being captured by the first positional parameter.

5. Since no positional argument is provided, `filepath` is missing → **TypeError**.

### Why Other Tools Work

All other `@file_tool`-decorated functions use `filepath` (matching the decorator):
- `read_file.py:36` → `filepath: str`
- `write_file.py:11` → `filepath: str`
- `update_file.py:13` → `filepath: str`

Only `limited_read_file` used `file_path` (with underscore).

## Fix Applied

Changed `file_path` to `filepath` in `research_agent.py:77-101`:

```python
# Before
async def limited_read_file(file_path: str) -> str:
    ...
    f"Cannot read '{file_path}' - ..."
    return await read_file(file_path)

# After
async def limited_read_file(filepath: str) -> str:
    ...
    f"Cannot read '{filepath}' - ..."
    return await read_file(filepath)
```

## Key Patterns / Solutions Found

- **`@file_tool` contract**: First parameter MUST be named `filepath` (no underscore)
- **Decorator signature preservation**: `@file_tool` uses `@wraps` and manually sets `__signature__`, creating a disconnect between runtime parameter names and introspected schema
- **pydantic-ai tool dispatch**: Uses signature introspection to determine keyword argument names when calling tools

## Knowledge Gaps

- Consider refactoring `@file_tool` to be parameter-name agnostic (extract first arg regardless of name)
- No test coverage caught this mismatch - could add a conformance test

## References

- `src/tunacode/core/agents/research_agent.py`
- `src/tunacode/tools/decorators.py`
- pydantic-ai `_function_schema.py:52` (call dispatch)
