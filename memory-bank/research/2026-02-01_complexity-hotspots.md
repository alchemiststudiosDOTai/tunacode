# Research – D-Grade Complexity Hotspots

**Date:** 2026-02-01
**Phase:** Research

## Overview

4 functions exceed McCabe complexity threshold (25):

| Function              | Score | File                                           | Threshold |
|-----------------------|-------|------------------------------------------------|-----------|
| `dispatch_tools`      | 29    | orchestrator/tool_dispatcher.py:219            | EXCEEDS   |
| `block_anchor_replacer` | 27  | tools/utils/text_match.py:162                  | EXCEEDS   |
| `process_node`        | 24    | orchestrator/orchestrator.py:180               | Below     |
| `is_ignored`          | 23    | configuration/ignore_patterns.py:84            | Below     |

---

## 1. `dispatch_tools` (Score: 29)

**File:** `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py:219`

### Signature
```python
async def dispatch_tools(
    parts: list[Any],
    node: Any,
    state_manager: StateManagerProtocol,
    tool_callback: ToolCallback | None,
    _tool_result_callback: ToolResultCallback | None,
    tool_start_callback: ToolStartCallback | None,
    response_state: ResponseState | None,
) -> ToolDispatchResult
```

### Complexity Breakdown

| Section                  | Lines     | Decision Points |
|--------------------------|-----------|-----------------|
| Primary loop (parts)     | 245-276   | 8               |
| Fallback extraction      | 278-291   | 5               |
| Tool execution           | 296-313   | 6               |
| State finalization       | 315-330   | 6               |
| Logging                  | 334-347   | 4               |
| **Total**                |           | **~29**         |

### Nested Complexity Sources
- Triple-nested: `debug_mode and _is_suspicious_tool_name(...)` inside loop (line 260)
- Triple-nested: `is_processing_tools and response_state and can_transition_to(...)` (lines 315-320)
- Double-nested with loop: `if tool_start_callback` inside `if tool_tasks and tool_callback` (line 301)

### Call Graph
```
ui/app.py → core/agents/main.py:process_request() → RequestOrchestrator.run()
    → process_node() → dispatch_tools()
```

### Extractable Subroutines
- `_process_native_tool_calls(parts, tool_callback, debug_mode)` → handle primary loop
- `_handle_fallback_parsing(tool_callback, response_parts)` → fallback extraction
- `_execute_tool_batch(tool_tasks, tool_callback, start_callback)` → tool execution
- `_finalize_dispatch_state(response_state, is_processing)` → state transition

---

## 2. `block_anchor_replacer` (Score: 27)

**File:** `src/tunacode/tools/utils/text_match.py:162`

### Signature
```python
def block_anchor_replacer(content: str, find: str) -> Generator[str, None, None]
```

### Complexity Breakdown

| Section                    | Lines     | Decision Points |
|----------------------------|-----------|-----------------|
| Preconditions              | 171-183   | 3               |
| Index building             | 185-196   | 4               |
| Candidate pair building    | 198-207   | 5               |
| Single candidate path      | 214-241   | 11              |
| Multiple candidates path   | 243-276   | 11              |
| **Total**                  |           | **~34** (actual ~27) |

### Key Issue: Mutually Exclusive Paths
Two large branches with **independent complexity**:
- Single candidate path: 11 decision points (lines 214-241)
- Multiple candidates path: 11 decision points (lines 243-276)

Both paths share similar logic (similarity calculation) but are duplicated.

### Nested Complexity Sources
- Triple-nested: `if max_len == 0` inside loop inside `if lines_to_check > 0` inside `if len(candidates) == 1`
- Double-nested loops: `for i in first_indices` → `for j in last_indices`

### Call Graph
```
tools/update_file.py:update_file() → text_match.py:replace()
    → block_anchor_replacer() (as generator)
```

### Extractable Subroutines
- `_calculate_similarity(content_lines, search_lines, start, end)` → used in BOTH paths
- `_build_candidate_pairs(first_indices, last_indices)` → nested loop extraction
- `_find_best_match(candidates, content_lines, search_lines)` → multiple candidate logic

---

## 3. `process_node` (Score: 24)

**File:** `src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py:180`

### Signature
```python
async def process_node(
    node: Any,
    tool_callback: ToolCallback | None,
    state_manager: StateManagerProtocol,
    _tool_buffer: ToolBuffer | None = None,
    _streaming_callback: StreamingCallback | None = None,
    response_state: ResponseState | None = None,
    tool_result_callback: ToolResultCallback | None = None,
    tool_start_callback: ToolStartCallback | None = None,
) -> tuple[bool, str | None]
```

### Complexity Breakdown

| Section                    | Lines     | Decision Points |
|----------------------------|-----------|-----------------|
| State transition (init)    | 206-214   | 2               |
| Request processing         | 216-219   | 1               |
| Thought processing         | 221-228   | 3               |
| Model response processing  | 230-285   | 14              |
| State finalization         | 287-292   | 3               |
| Return logic               | 294-300   | 2               |
| **Total**                  |           | **~25** (actual ~24) |

### Key Issue: Long Conditional Chain
`if model_response is not None` block (lines 231-285) contains:
- Debug logging branch
- Response state processing
- Content extraction loop with 2 branches
- Content combination block
- Empty response detection
- Tool dispatch call

### Nested Complexity Sources
- Triple-nested: `if content.strip()` inside loop inside `if response_state` inside `if model_response`
- Triple condition: `if response_state and can_transition_to(...) and not is_completed()`

### Call Graph
```
core/agents/main.py:RequestOrchestrator.run() → process_node()
    → dispatch_tools() (complexity 29)
```

### Extractable Subroutines
- `_process_model_response(model_response, response_state, debug_mode)` → entire lines 231-285
- `_extract_content_parts(response_parts)` → content extraction loop
- `_detect_empty_response(parts_result, response_state)` → empty detection logic

---

## 4. `is_ignored` (Score: 23)

**File:** `src/tunacode/configuration/ignore_patterns.py:84`

### Signature
```python
def is_ignored(rel_path: str, name: str, patterns: Iterable[str]) -> bool
```

### Complexity Breakdown

| Section                    | Lines     | Decision Points |
|----------------------------|-----------|-----------------|
| Early exit checks          | 86-92     | 4               |
| Rooted pattern branch      | 100-110   | 10              |
| Name match                 | 112-113   | 2               |
| Full path match            | 115-116   | 1               |
| Path components loop       | 118-124   | 5               |
| Outer loop + entry         | 96, 126   | 2               |
| **Total**                  |           | **~24** (actual ~23) |

### Key Issue: Deep Nesting in Rooted Patterns
```
for pattern in patterns:           # level 1
    if starts_with("/"):           # level 2
        if fnmatch(...):           # level 3
            if is_dir_pattern:     # level 4
                if exact_match:    # level 5 (!)
```

### Nested Complexity Sources
- Quadruple-nested: `if rel_path == match_pattern or ...` inside `if is_dir_pattern` inside `if fnmatch(...)` inside loop
- Triple-nested: `if fnmatch.fnmatch(path_parts[i], ...)` inside inner loop inside `if is_dir_pattern or...`
- Nested loop: `for i in range(limit)` inside `for pattern in patterns`

### Call Graph
```
utils/system/gitignore.py:72,78 → is_ignored()
infrastructure/file_filter.py:37 → is_ignored() (different signature)
tools/glob.py, tools/grep.py, tools/list_dir.py → use FileFilter → is_ignored()
```

### Note: Two Implementations
1. `configuration/ignore_patterns.py:84` - Pure function (this one, score 23)
2. `infrastructure/file_filter.py:37` - Method on `FileFilter` class (different signature)

### Extractable Subroutines
- `_match_rooted_pattern(rel_path, pattern, is_dir_pattern)` → entire lines 100-110
- `_match_path_components(path_parts, pattern, is_dir_pattern)` → lines 118-124

---

## Common Patterns Across All Functions

### 1. Long Sequential Branches
All functions have 15+ sequential decision points in a single function body.

### 2. Deep Nesting (3-4 levels)
| Function              | Max Nesting |
|-----------------------|-------------|
| `dispatch_tools`      | 3           |
| `block_anchor_replacer` | 4         |
| `process_node`        | 3           |
| `is_ignored`          | 5           |

### 3. Loops with Multiple Internal Branches
| Function              | Loop        | Internal Branches |
|-----------------------|-------------|-------------------|
| `dispatch_tools`      | `for part`  | 5                 |
| `block_anchor_replacer` | nested    | 6 each            |
| `process_node`        | `for part`  | 2                 |
| `is_ignored`          | nested      | 3                 |

### 4. No Subroutine Extraction
All functions keep related logic inline rather than extracting helper functions.

---

## Dependency Layer Map

```
UI Layer
  └── ui/app.py → process_request()
        │
Core Layer
  └── core/agents/main.py → RequestOrchestrator.run()
        │
        ├── orchestrator/orchestrator.py:process_node() [24]
        │     └── orchestrator/tool_dispatcher.py:dispatch_tools() [29]
        │
Tools Layer
  └── tools/update_file.py → update_file()
        └── tools/utils/text_match.py:block_anchor_replacer() [27]

Configuration Layer
  └── configuration/ignore_patterns.py:is_ignored() [23]
        ↑ used by
        ├── utils/system/gitignore.py
        ├── infrastructure/file_filter.py
        └── tools/{glob,grep,list_dir}.py (via FileFilter)
```

---

## Test Coverage

| Function              | Test File                                    |
|-----------------------|----------------------------------------------|
| `dispatch_tools`      | tests/integration/tools/test_tool_dispatcher_coverage.py |
| `block_anchor_replacer` | tests/unit/core/test_text_match.py         |
| `process_node`        | tests/integration/core/test_tool_call_lifecycle.py |
| `is_ignored`          | tests/tools/test_ignore.py                   |

---

## Files Touched (Full Paths)

### dispatch_tools
- `/home/tuna/tunacode/src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
- `/home/tuna/tunacode/src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py`
- `/home/tuna/tunacode/src/tunacode/core/agents/main.py`

### block_anchor_replacer
- `/home/tuna/tunacode/src/tunacode/tools/utils/text_match.py`
- `/home/tuna/tunacode/src/tunacode/tools/update_file.py`

### process_node
- `/home/tuna/tunacode/src/tunacode/core/agents/agent_components/orchestrator/orchestrator.py`
- `/home/tuna/tunacode/src/tunacode/core/agents/main.py`
- `/home/tuna/tunacode/src/tunacode/ui/app.py`

### is_ignored
- `/home/tuna/tunacode/src/tunacode/configuration/ignore_patterns.py`
- `/home/tuna/tunacode/src/tunacode/infrastructure/file_filter.py`
- `/home/tuna/tunacode/src/tunacode/utils/system/gitignore.py`
