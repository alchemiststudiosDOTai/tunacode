# Research - LSP Feedback Not Acting on Subagents

**Date:** 2025-12-18
**Owner:** agent
**Phase:** Research

## Goal

Investigate why subagents see LSP diagnostics in the UI but don't act on them as feedback. Compare tunacode's approach with opencode's implementation.

## Problem Statement

From screenshot analysis:
- UI displays "LSP Diagnostics 6 warnings" with specific issues (L76 Unnecessary mode argument, L298 Use f-string, L306 Ambiguous variable name, lines too long)
- Subagent reports "successfully expanded the dummy.py file" without addressing any warnings
- User expects agent to fix LSP issues automatically

## Findings

### Tunacode's Current Implementation

**Diagnostics ARE injected into tool results:**
- `src/tunacode/tools/decorators.py:186-190` - `@file_tool(writes=True)` decorator
- Diagnostics prepended as XML: `<file_diagnostics>...</file_diagnostics>`
- Agent receives full string including diagnostics in message history

**Flow:**
1. `update_file()` completes write
2. Decorator calls `_get_lsp_diagnostics(filepath)`
3. XML block prepended to result string
4. Result goes to pydantic-ai as tool-return
5. Agent sees diagnostics in context

**Key files:**
- `src/tunacode/tools/decorators.py:58-86` - LSP fetch logic
- `src/tunacode/lsp/__init__.py:82-111` - XML formatting
- `src/tunacode/ui/renderers/tools/diagnostics.py` - UI extraction/display

### The Gap: Passive vs Active Feedback

**Tunacode (passive):**
```
<file_diagnostics>
Summary: 0 errors, 6 warnings
Warning (line 76): Unnecessary mode argument
...
</file_diagnostics>

File 'path' updated successfully.
```

The agent sees this but there's **no instruction to act on it**. The diagnostics are informational, not actionable commands.

### Opencode's Approach (Active)

From `packages/opencode/src/tool/edit.ts`:

```typescript
await LSP.touchFile(filePath, true)
const diagnostics = await LSP.diagnostics()
const issues = diagnostics[normalizedFilePath] ?? []

// Filter for ERRORS (severity 1) and include in output
```

**Key differences:**
1. **Dedicated tool**: `LspDiagnosticTool` - agent can actively request diagnostics
2. **Error filtering**: Only severity=1 (errors) included in edit response
3. **Explicit output**: Errors formatted into response text, not just metadata

### Why Subagents Don't Act

1. **No explicit instruction**: System prompt doesn't tell agent to fix LSP issues
2. **Warnings vs Errors**: 6 warnings shown, but warnings often ignored
3. **Task completion bias**: Agent considers task "done" after successful write
4. **Context separation**: Subagents may have minimal system prompts

## Key Patterns / Solutions Found

### Pattern 1: Explicit Error Handling in Tool Response
OpenCode filters for `severity=1` (errors) and includes them explicitly:
```
Edit successful but found 3 errors:
- Line 45: Undefined variable 'foo'
Please fix these before continuing.
```

### Pattern 2: Dedicated Diagnostics Tool
OpenCode has `LspDiagnosticTool` that agent can call proactively. Agent can:
- Check file before edit
- Check file after edit
- Decide whether to fix issues

### Pattern 3: Error-Driven Retry Loop
If errors exist after write, return a result that triggers agent to retry:
```
File written but contains errors. Fix required:
- Error (line 45): ...
```

## Recommended Fixes for Tunacode

### Option A: Make Write Tool Response Error-Aware
In `decorators.py`, change how diagnostics affect the result:

```python
if writes:
    diagnostics_output = await _get_lsp_diagnostics(filepath)
    if diagnostics_output:
        # Count errors specifically
        error_count = diagnostics_output.count("Error (line")
        if error_count > 0:
            result = f"File written but contains {error_count} errors that must be fixed:\n{diagnostics_output}\n\n{result}"
        else:
            result = f"{diagnostics_output}\n\n{result}"
```

### Option B: Add Explicit Diagnostics Tool
Create `check_diagnostics` tool that agent can call:
- After edits to verify quality
- Before committing changes
- Proactively on suspicious files

### Option C: Enhance Subagent System Prompts
Add to subagent instructions:
```
After any file write, check the tool result for <file_diagnostics>.
If errors exist, fix them before reporting success.
Warnings should be addressed if they indicate code quality issues.
```

## Knowledge Gaps

- How does pydantic-ai handle tool retries based on result content?
- Can we add a "post-tool hook" that validates results?
- Should subagents have different LSP behavior than main agent?

## References

- `src/tunacode/tools/decorators.py` - Current LSP injection
- `src/tunacode/lsp/__init__.py` - Diagnostics formatting
- `src/tunacode/ui/renderers/tools/diagnostics.py` - UI rendering
- https://github.com/sst/opencode/blob/0b286f1b840ed3b1ac1a771becf2fad0b9b9a624/packages/opencode/src/tool/lsp-diagnostics.ts - OpenCode dedicated tool
- https://github.com/sst/opencode - OpenCode edit.ts LSP integration
