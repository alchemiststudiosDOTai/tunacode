# CLI Agent Incident Report: Invalid JSON Tool Args Not Retried

**Date:** 2025-08-12
**Agent:** Claude Code CLI
**Severity:** Medium
**Status:** ✅ RESOLVED

## Summary

The CLI agent failed with "Invalid JSON … Extra data" error when the model emitted multiple concatenated JSON objects as tool arguments. The retry mechanism did not trigger, causing workflow interruption and user-visible error.

## Problem Description

- **Symptom:** ValidationError with "Invalid JSON with concatenated objects"
- **Error:** JSONDecodeError: Extra data
- **Example malformed input:** `{"filepath": "main.py"}{"filepath": "__init__.py"}{"filepath": "cli/main.py"}`
- **Expected:** Single JSON object or proper array structure
- **Impact:** Tool call aborted at parse stage, no retry attempted

## Investigation Findings

### 1. Failure Point: Strict JSON Parsing
**Location:** `src/tunacode/cli/repl_components/command_parser.py:13-34`

```python
def parse_args(args) -> ToolArgs:
    if isinstance(args, str):
        try:
            return json.loads(args)  # ← Fails here with "Extra data"
        except json.JSONDecodeError:
            raise ValidationError(f"Invalid JSON: {args}")
```

- Uses strict `json.loads()` which rejects concatenated JSON objects
- Re-raises JSONDecodeError as ValidationError with "Invalid JSON" prefix
- No tolerance for NDJSON or concatenated objects

### 2. Tool Execution Flow
**Location:** `src/tunacode/cli/repl_components/tool_executor.py:59`

```python
try:
    args = parse_args(part.args)  # ← Exception thrown here
```

- Failure occurs before any tool execution
- Exception propagates up to generic handler in repl.py

### 3. Error Recovery Mechanism
**Location:** `src/tunacode/cli/repl_components/error_recovery.py:19-88`

#### Keyword Filtering (Lines 26-29)
```python
error_str = str(e).lower()
tool_keywords = ["tool", "function", "call", "schema"]
if not any(keyword in error_str for keyword in tool_keywords):
    return False  # ← Exits immediately
```

- **Issue:** "Invalid JSON" error doesn't contain required keywords
- **Result:** Recovery returns False without attempting remediation

#### Recovery Strategy Mismatch (Lines 38-68)
```python
for part in last_msg.parts:
    content_to_parse = getattr(part, "content", None)
    # ... parses tool calls from plain text content
```

- **Design:** Recovers text-dumped tool calls from message content
- **Problem:** Cannot repair malformed `args` within structured tool-call parts
- **Gap:** No mechanism to handle concatenated JSON objects in `args` field

### 4. Exception Handler
**Location:** `src/tunacode/cli/repl.py:372`

```python
except Exception as e:
    if not await attempt_tool_recovery(e, state_manager):
        await ui.error(str(e))  # ← User sees raw error
```

- Only displays error if recovery fails
- No fallback mechanisms for JSON parsing failures

## Root Cause Analysis

### Primary Cause
**Model Contract Violation:** The model emitted multiple JSON objects for a single tool call instead of:
- One JSON object per tool call, OR
- A single object with array field (e.g., `{"filepaths": ["a.py", "b.py"]}`)

### Secondary Causes
1. **Narrow Recovery Heuristics:** Keyword filtering excludes JSON parsing errors
2. **Recovery Strategy Mismatch:** Recovery designed for text-dumped tools, not malformed structured args
3. **Strict Parser:** No tolerance for common JSON concatenation patterns

## Why Recovery Failed

1. **Heuristic Miss:** Error message lacked keywords ("tool", "function", "call", "schema")
2. **Wrong Recovery Mode:** Recovery parses tools from text content, not from malformed `args` in structured tool-call parts
3. **No JSON-Specific Remediation:** No handling for concatenated JSON objects or similar malformed patterns

## Recommendations

### 1. Prompt Engineering (High Priority)
- **Tool Schema Enforcement:** Update tool descriptions to explicitly require "exactly one JSON object" for args
- **System Guidance:** Add instruction: "Never output multiple JSON objects for tool arguments"
- **Array Fields:** Encourage use of list fields for multiple items (e.g., `{"filepaths": [...]`)

### 2. Parser Resilience (Medium Priority)
For read-only tools only:
- **Safe Splitting:** On "Extra data" errors, attempt to split concatenated objects
- **Execution Options:**
  - Multiple tool calls (one per object)
  - Merge into array field if tool supports it
- **Safety Gate:** Require confirmation or restrict to read-only operations

### 3. Recovery Enhancement (Medium Priority)
- **Broader Keywords:** Include "json", "jsondecodeerror", "extra data", "invalid json"
- **JSON-Specific Recovery:** Add remediation path for malformed `args` in structured tool calls
- **Targeted Splitting:** Implement safe concatenated JSON object splitting

### 4. Monitoring (Low Priority)
- **Error Classification:** Track JSON parsing failures vs. other tool errors
- **Model Behavior:** Monitor frequency of concatenated JSON emissions
- **Recovery Effectiveness:** Measure success rates of different recovery strategies

## Next Steps

1. **Immediate:** Update system prompts to prevent concatenated JSON objects
2. **Short-term:** Broaden recovery heuristics to include JSON error indicators
3. **Medium-term:** Implement safe JSON object splitting for read-only tools
4. **Long-term:** Consider NDJSON tolerance for specific tool types

## References

- **Command Parser:** `src/tunacode/cli/repl_components/command_parser.py:13-34`
- **Tool Executor:** `src/tunacode/cli/repl_components/tool_executor.py:59`
- **Error Recovery:** `src/tunacode/cli/repl_components/error_recovery.py:19-88`
- **Exception Handler:** `src/tunacode/cli/repl.py:372`

## Resolution Summary

**Implementation Date:** 2025-08-12
**Commit:** cba0108f - "feat: implement comprehensive JSON concatenation recovery system"

### What Was Implemented

1. **Enhanced parse_args()** with retry logic and concatenated JSON fallback handling
2. **New json_utils.py module** with robust JSON splitting and safety validation
3. **Extended error recovery** keywords to include JSON-specific terms
4. **Updated system prompt** with explicit JSON formatting guidelines
5. **Comprehensive test suite** (33 tests) covering all recovery scenarios

### Key Features
- **Transient Failure Recovery:** Exponential backoff retry for temporary JSON parsing issues
- **Concatenated Object Splitting:** Safe parsing of `{"a":1}{"b":2}` patterns
- **Safety Validation:** Read-only tools can execute multiple objects, write tools use first object only
- **Transparent Recovery:** Users see successful execution instead of cryptic JSON errors
- **Backward Compatibility:** Single JSON objects continue to work as before

### Files Modified
- `src/tunacode/cli/repl_components/command_parser.py` - Enhanced parse_args()
- `src/tunacode/utils/json_utils.py` - New utility module (207 lines)
- `src/tunacode/cli/repl_components/error_recovery.py` - JSON error keywords
- `src/tunacode/prompts/system.md` - JSON formatting rules
- `tests/test_command_parser_retry.py` - Retry logic tests
- `tests/test_json_concatenation_recovery.py` - Concatenation recovery tests

### Verification
✅ All 33 tests pass
✅ Handles concatenated JSON objects gracefully
✅ Maintains safety for write operations
✅ Preserves backward compatibility
✅ Improves error recovery coverage

---
*Investigation completed: 2025-08-12*
*Resolution implemented: 2025-08-12*
*Status: Closed - Recovery system active*
