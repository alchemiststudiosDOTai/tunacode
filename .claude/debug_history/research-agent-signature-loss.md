---
title: Research Agent Tool Wrapper Loses Function Signature
link: research-agent-signature-loss
type: delta
path: debug_history/
depth: 1
seams: [M]
ontological_relations:
  - relates_to: [[pydantic-ai]]
  - affects: [[research_agent]]
  - fixes: [[ToolExecutionError-dict-instead-of-str]]
tags:
  - pydantic-ai
  - tool-schema
  - inspect-signature
  - research-agent
created_at: 2026-01-09T20:30:00Z
updated_at: 2026-01-09T20:30:00Z
uuid: a27b911e-d6e9-4c0d-9149-ba04f9b393c1
---

## Problem

Research agent tools (`grep`, `read_file`, etc.) receiving dict arguments instead of strings, causing errors like:

```
Tool 'grep' failed: argument should be a str or an os.PathLike object, not 'dict'
Tool 'read_file' failed: stat: path should be string, bytes, os.PathLike or integer, not dict
```

## Root Cause

`ProgressTracker.wrap_tool()` in `research_agent.py` creates wrapper functions with `*args, **kwargs` signature:

```python
async def wrapped(*args, **kwargs) -> Any:
    self.emit(operation)
    return await tool_func(*args, **kwargs)

wrapped.__name__ = tool_func.__name__
wrapped.__doc__ = tool_func.__doc__
wrapped.__annotations__ = getattr(tool_func, "__annotations__", {})
# MISSING: __signature__
```

pydantic-ai uses `inspect.signature()` to generate JSON schemas for tool calls. When it inspects wrapped functions:

- **Original grep**: `(pattern: str, directory: str = '.', ...) -> str`
- **Wrapped grep**: `(*args, **kwargs) -> Any`

Without proper signature, pydantic-ai can't tell the LLM what types each parameter expects. The LLM hallucinates argument structures, sometimes passing dicts where strings are expected.

## Solution

Add `__signature__` preservation to the wrapper:

```python
wrapped.__signature__ = inspect.signature(tool_func)
```

**File**: `src/tunacode/core/agents/research_agent.py`

**Diff**:
```diff
+import inspect
 from pathlib import Path
 from typing import Any

         wrapped.__name__ = tool_func.__name__
         wrapped.__doc__ = tool_func.__doc__
         wrapped.__annotations__ = getattr(tool_func, "__annotations__", {})
+        wrapped.__signature__ = inspect.signature(tool_func)
```

## Why `__annotations__` Wasn't Enough

- `__annotations__` is a dict mapping parameter names to types
- `inspect.signature()` returns a `Signature` object with parameter order, defaults, and kinds
- pydantic-ai prefers `inspect.signature()` over `__annotations__` for schema generation

## Verification

```python
import inspect
from tunacode.core.agents.research_agent import ProgressTracker
from tunacode.tools.grep import grep

tracker = ProgressTracker(None)
wrapped = tracker.wrap_tool(grep, 'grep')

# Before fix: (*args, **kwargs) -> Any
# After fix:  (pattern: str, directory: str = '.', ...) -> str
print(inspect.signature(wrapped))
```

## Lesson

When wrapping async functions for pydantic-ai tools, always preserve:
1. `__name__`
2. `__doc__`
3. `__annotations__`
4. `__signature__` (critical for schema generation)

Or use `functools.wraps()` which handles most of these, then manually add `__signature__`.
