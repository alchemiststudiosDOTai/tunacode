# Research - Stacked Tool Call UI

**Date:** 2026-02-04
**Owner:** Claude
**Phase:** Research
**Branch:** stack-tool-calls

## Goal

Research how to implement stacked/compressed tool call display when >3 tool calls occur in a single response, matching the dream UI design in `docs/images/dream-ui/tunacode-cli-response.png`.

## Dream UI Reference

The target design shows tool calls stacked compactly:
```
> glob       [ *.json ]
> read_file  index.html
> read_file  claude_code_mcp.md
> list_dir   articles
```

Key characteristics:
- Compact single-line per tool
- Tool name left-aligned, key argument right
- No full panels - just summary rows
- No timestamps needed (batch renders after completion)
- Visual grouping of related tool calls

## Current Architecture

### Data Flow

```
1. Agent model returns tool-call parts
   |
2. tool_dispatcher.py:260-292 collects into tool_tasks list
   |
3. tool_dispatcher.py:325-329 executes via execute_tools_parallel()
   |
4. orchestrator.py:67 emits tool returns one-by-one via _emit_tool_returns()
   |
5. repl_support.py:165 posts ToolResultDisplay message (per tool)
   |
6. app.py:284 on_tool_result_display() renders panel immediately
   |
7. panels.py:479 tool_panel_smart() routes to specific renderer
   |
8. chat_container.write() mounts as Static widget
```

### Key Problem

Each tool result triggers an independent `ToolResultDisplay` message and immediate render. **No batching or grouping exists at the UI level.**

### Existing Batch Information (Not Exposed to UI)

The orchestrator already tracks batches:
- `runtime.batch_counter` incremented per tool batch
- `TOOL_BATCH_PREVIEW_COUNT = 3` used for status bar preview
- Status bar shows: `"glob, grep, read_file..."` during execution

## Findings

### Relevant Files

| File | Purpose |
|------|---------|
| `src/tunacode/ui/app.py:284-294` | Message handler - renders each tool immediately |
| `src/tunacode/ui/repl_support.py:147-175` | Callback factory - posts ToolResultDisplay |
| `src/tunacode/ui/widgets/messages.py:30-47` | ToolResultDisplay message class |
| `src/tunacode/ui/renderers/panels.py:479-534` | tool_panel_smart() router |
| `src/tunacode/ui/renderers/tools/base.py:287-481` | BaseToolRenderer 4-zone pattern |
| `src/tunacode/ui/widgets/chat.py:54-81` | ChatContainer.write() mounts panels |
| `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py:314-323` | Batch counter and preview |

### Interception Points (Ranked by Pragmatism)

**1. Message Handler Level (Recommended)**
- Location: `app.py:284 on_tool_result_display()`
- Approach: Buffer incoming messages, debounce, render batch as stacked view
- Pros: Localized change, no callback signature changes
- Cons: Timing-based batching may miss late arrivals

**2. Callback + Orchestrator Level**
- Location: `repl_support.py` callback + `orchestrator.py` emit
- Approach: Add `batch_id` and `batch_total` to ToolResultDisplay
- Pros: Explicit batch semantics, guaranteed grouping
- Cons: Requires changes across multiple files

**3. New Stacked Renderer**
- Location: `src/tunacode/ui/renderers/tools/stacked.py` (new)
- Approach: Create renderer that accepts list of tool results
- Pros: Clean separation, reusable
- Cons: Still needs orchestration from app.py

## Proposed Implementation

### Option A: Debounce-Based Batching (Simplest)

```python
# app.py
_tool_result_buffer: list[ToolResultDisplay] = []
_batch_timer: Timer | None = None
BATCH_DEBOUNCE_MS = 50  # Wait 50ms after last tool result

def on_tool_result_display(self, message: ToolResultDisplay) -> None:
    self._tool_result_buffer.append(message)
    if self._batch_timer:
        self._batch_timer.cancel()
    self._batch_timer = self.set_timer(
        BATCH_DEBOUNCE_MS / 1000,
        self._flush_tool_results
    )

def _flush_tool_results(self) -> None:
    if len(self._tool_result_buffer) > 3:
        self._render_stacked_tools(self._tool_result_buffer)
    else:
        for msg in self._tool_result_buffer:
            self._render_single_tool(msg)
    self._tool_result_buffer.clear()
```

### Option B: Explicit Batch Tracking (More Robust)

1. Add to `ToolResultDisplay`:
   ```python
   batch_id: str | None = None
   batch_total: int | None = None
   ```

2. Modify `tool_dispatcher.py` to generate batch_id (UUID) per dispatch

3. Modify `orchestrator.py._emit_tool_returns()` to pass batch info

4. Buffer in `app.py` until `len(buffer) == batch_total`

### Stacked Renderer Component

New file: `src/tunacode/ui/renderers/tools/stacked.py`

```python
def render_stacked_tools(
    tools: list[ToolResultDisplay],
    max_line_width: int,
) -> Panel:
    """Render multiple tools as compact stacked rows."""
    rows = []
    for tool in tools:
        key_arg = _extract_key_arg(tool.name, tool.args)
        row = Text()
        row.append("> ", style="dim")
        row.append(f"{tool.name:<12}", style="cyan bold")
        row.append(key_arg, style="yellow")
        rows.append(row)

    return Panel(
        Group(*rows),
        title="[cyan]Tool Batch[/]",
        border_style="dim",
    )
```

## Key Patterns / Solutions Found

- **Batch Counter Exists**: `tool_dispatcher.py:314` already increments batch counter
- **Preview Logic Reusable**: `TOOL_BATCH_PREVIEW_COUNT = 3` constant matches our threshold
- **4-Zone Pattern**: Existing renderers follow template method pattern in `base.py`
- **Message-Driven UI**: Textual message system allows clean decoupling

## Knowledge Gaps

- Timer behavior in Textual during high tool throughput
- Whether batch_id should be UUID or simple counter
- Interaction with session replay (`_replay_session_messages`)
- How stacked view should handle failures (red row? expand?)

## Implementation Recommendation

Start with **Option A (Debounce)** for quick iteration:
1. Add buffer and timer to `app.py`
2. Create `stacked.py` renderer
3. Test with 5-10 concurrent tool calls
4. If timing issues emerge, upgrade to **Option B**

## References

- Dream UI: `docs/images/dream-ui/tunacode-cli-response.png`
- Tool dispatcher: `src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py`
- Panel renderer: `src/tunacode/ui/renderers/panels.py`
- Base renderer: `src/tunacode/ui/renderers/tools/base.py`
- App handler: `src/tunacode/ui/app.py:284-294`
