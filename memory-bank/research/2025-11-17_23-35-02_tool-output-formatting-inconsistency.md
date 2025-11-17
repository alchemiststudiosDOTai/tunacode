# Research – Tool Output Formatting Inconsistency

**Date:** 2025-11-17T23:35:02Z
**Owner:** context-engineer:research agent
**Phase:** Research
**Git Commit:** 6baced4d773ec29dc747ea926163b0f00b8ccab4
**Branch:** master

## Goal

Investigate the formatting inconsistency between the "nice blue UI boxes" (styled agent output panels) and the "ugly parallel tool calls" (plain text batch execution output) to understand why different formatting approaches are used and map the architectural separation.

## Context

User observed that agent responses are displayed in attractive cyan-bordered Rich panels with rounded boxes, markdown rendering, and consistent padding, while parallel batch tool execution output uses plain text with ASCII separators (`=` characters) and no visual styling. This creates a visual inconsistency in the CLI experience.

## Research Approach

Deployed three parallel codebase-locator and codebase-analyzer agents to:
1. Locate all parallel batch output formatting code
2. Find blue UI box formatting implementation
3. Analyze the overall output formatting architecture and decision logic

## Findings

### Parallel Batch Output Formatting

**Primary Implementation:**
- [node_processor.py:382-416](src/tunacode/core/agents/agent_components/node_processor.py#L382-L416) - Main parallel batch formatting
  - Uses plain text with `"=" * 60` separators
  - Outputs batch headers: `"PARALLEL BATCH #{batch_id}: Executing {count} read-only tools concurrently"`
  - Displays numbered tool list with arguments
  - Shows performance metrics: `"Parallel batch completed in {time}ms (~{speedup}x faster than sequential)"`
  - All output via `ui.muted()` function

**Secondary Implementation:**
- [main.py:312-350](src/tunacode/core/agents/main.py#L312-L350) - Final batch formatting
  - Similar plain text formatting pattern
  - Outputs `"FINAL BATCH: Executing {count} buffered read-only tools"`
  - Same performance metrics display

**Output Function:**
- [output.py:93-95](src/tunacode/ui/output.py#L93-L95) - `muted()` function
  ```python
  async def muted(text: str) -> None:
      """Print muted text."""
      await print(text, style=colors.muted)
  ```
  - Applies muted color styling but no panel/box formatting

**Batch Description:**
- [tool_descriptions.py:91-115](src/tunacode/ui/tool_descriptions.py#L91-L115) - Dynamic batch messages
  - Generates context-aware descriptions: "Reading N files in parallel", "Searching N patterns in parallel"

### Blue UI Box Formatting

**Primary Panel Implementation:**
- [panels.py:81-107](src/tunacode/ui/panels.py#L81-L107) - Generic `panel()` function
  ```python
  async def panel(
      title: str,
      text: Union[str, "Markdown", "Pretty", "Table"],
      border_style: Optional[str] = None,
      **kwargs
  ):
      # Creates Rich Panel with ROUNDED box style
      # Markdown content rendering
      # Consistent padding
  ```

**Agent-Specific Panel:**
- [panels.py:110-114](src/tunacode/ui/panels.py#L110-L114) - `agent()` function
  ```python
  async def agent(text: str, bottom: int = 1) -> None:
      title = f"[bold {colors.primary}]●[/bold {colors.primary}] {APP_NAME}"
      await panel(title, rich["Markdown"](text), bottom=bottom, border_style=colors.primary)
  ```
  - Cyan bullet point and border (`colors.primary` = `#00d7ff`)
  - Rounded box style
  - Markdown rendering for content

**Streaming Panel:**
- [panels.py:117-349](src/tunacode/ui/panels.py#L117-L349) - `StreamingAgentPanel` class
  - Progressive rendering with Rich.Live
  - Animated dots during thinking
  - Same rounded box styling as static panels

**Color Definitions:**
- [constants.py:107-118](src/tunacode/constants.py#L107-L118) - `UI_COLORS` dictionary
  - `"primary": "#00d7ff"` - Bright cyan for panel borders
  - `"muted": "#64748b"` - Slate gray for diagnostic output
  - `"border": "#475569"` - Stronger slate border

**Rich Components:**
- [panels.py:52-78](src/tunacode/ui/panels.py#L52-L78) - Lazy-loaded Rich imports
  - ROUNDED box style
  - Panel, Padding, Markdown classes
  - Cached for performance

### Output Formatting Architecture

**Decision Tree Root:**
- [repl.py:141-168](src/tunacode/cli/repl.py#L141-L168) - Primary formatting decision point
  ```python
  enable_streaming = user_config.get("settings", {}).get("enable_streaming", True)

  if enable_streaming:
      # Create StreamingAgentPanel with callback
      streaming_panel = ui.StreamingAgentPanel(...)
      res = await agent.process_request(
          streaming_callback=lambda content: streaming_panel.update(content),
          ...
      )
  else:
      # Non-streaming path displays output at end
      await display_agent_output(res, enable_streaming, state_manager)
  ```

**Output Display Logic:**
- [output_display.py:13-45](src/tunacode/cli/repl_components/output_display.py#L13-L45) - Non-streaming output
  - Filters system prompts and JSON thought objects
  - Displays via `ui.agent()` which uses Rich panels
  - Skips output if streaming was active

**Core Print Wrapper:**
- [output.py:67-70](src/tunacode/ui/output.py#L67-L70) - Async print function
  ```python
  @create_sync_wrapper
  async def print(message, **kwargs) -> None:
      await run_in_terminal(lambda: console.print(message, **kwargs))
  ```
  - Integrates with prompt_toolkit terminal
  - Routes all output through Rich console

**Logging Integration:**
- [logging_compat.py:12-44](src/tunacode/ui/logging_compat.py#L12-L44) - `UnifiedUILogger`
  - Routes `info()`, `success()`, `warning()` calls to core logger
  - Allows filtering and structured output

## Key Patterns / Solutions Found

### 1. **Architectural Separation Pattern**

The formatting inconsistency is **intentional and architectural**:

- **Agent responses** (user-facing content) → Rich panels with styling
- **Tool execution diagnostics** (system-level output) → Plain text via `muted()` function
- **Streaming agent output** → Rich.Live panels with progressive updates

This separation reflects different output purposes:
- Agent panels emphasize important user-facing content
- Tool execution output provides technical diagnostics without visual distraction

### 2. **Lazy Initialization Performance Pattern**

[output.py:30-50](src/tunacode/ui/output.py#L30-L50) and [panels.py:52-78](src/tunacode/ui/panels.py#L52-L78)

- Rich library components loaded only on first use
- `_LazyConsole` proxy defers console creation
- `get_rich_components()` caches Panel, Markdown, etc.
- Reduces CLI startup time

### 3. **Strategy Pattern for Output Format Selection**

Three distinct formatting strategies:
1. **Streaming Strategy**: [panels.py:117-349](src/tunacode/ui/panels.py#L117-L349) - `StreamingAgentPanel` with token deltas
2. **Batch Strategy**: [node_processor.py:315-422](src/tunacode/core/agents/agent_components/node_processor.py#L315-L422) - Plain text metrics
3. **Non-Streaming Strategy**: [output_display.py:13-45](src/tunacode/cli/repl_components/output_display.py#L13-L45) - Post-completion Rich panels

### 4. **Callback-Based Token Streaming**

[repl.py:166](src/tunacode/cli/repl.py#L166) and [streaming.py:24](src/tunacode/core/agents/agent_components/streaming.py#L24)

```python
streaming_callback=lambda content: streaming_panel.update(content)
```

- Decouples token source from display
- Allows flexible rendering strategies
- Enables real-time updates without blocking

### 5. **Buffer Pattern for Tool Batching**

[node_processor.py:315-422](src/tunacode/core/agents/agent_components/node_processor.py#L315-L422)

- Collects read-only tools into parallel batches
- Executes write/execute tools sequentially
- Displays batch metadata and performance metrics in plain text

### 6. **Guard-Clause Based Content Filtering**

[output_display.py:18-42](src/tunacode/cli/repl_components/output_display.py#L18-L42)

- Early returns for empty results
- Filters system prompts: `"namespace functions {"`, `"namespace multi_tool_use {"`
- Skips JSON thought objects
- Prevents technical noise in user-facing output

## Knowledge Gaps

### Why Plain Text for Tool Execution?

**RESOLVED:** Git history investigation revealed the design rationale.

**Git History Analysis:**

Commit [8ea04d5](https://github.com/alchemiststudiosDOTai/tunacode/commit/8ea04d56f25d4fcb34cfbda0b8699be2dff92ef2) (2025-11-17):
- **"fix: remove emojis from parallel batch output and add research doc"**
- Changed from `f"🚀 PARALLEL BATCH #{batch_id}:"` to plain text
- Changed from `f"✅ Parallel batch completed"` to plain text
- Rationale: User preference against emojis (per CLAUDE.md instructions)

Commit [ee9789c](https://github.com/alchemiststudiosDOTai/tunacode/commit/ee9789c9fcbde569fd536fb8a5eb4d8a9c2f1d6a) (2025-11-17):
- **"feat: extensive refactoring and cleanup across agent system and test suite"**
- Introduced enhanced parallel execution with batch UI messages
- Added visual feedback using `ui.muted()` with separators
- Implementation focused on performance visibility rather than styling

**Design Decisions:**

1. **User Preference**: The user explicitly dislikes emojis (documented in `.claude/CLAUDE.md` and `~/.claude/CLAUDE.md`)
2. **Visual Hierarchy**: Muted diagnostic output doesn't compete with agent responses (intentional)
3. **Implementation Velocity**: Focus was on parallel execution functionality, not UI polish
4. **No Technical Constraints**: There are **no technical reasons** preventing Rich panel usage

**Conclusion:** Plain text was chosen for simplicity and user preference, not performance or technical limitations. Rich panels are **absolutely viable** for tool execution output.

### Potential Improvements

To align tool execution output with agent panel styling:

1. **Create dedicated batch panel function** similar to `ui.agent()`:
   ```python
   async def batch_panel(batch_id: int, tool_count: int, tools: list, elapsed_ms: float):
       # Use Rich Panel with border_style=colors.secondary
       # Format tool list as Table or structured Markdown
   ```

2. **Use Rich Table for tool list** instead of plain numbered list:
   ```python
   table = Table(show_header=True, border_style=colors.secondary)
   table.add_column("Tool", style="cyan")
   table.add_column("Arguments", style="dim")
   for tool in tools:
       table.add_row(tool.name, format_args(tool.args))
   ```

3. **Consistent separator styling** using Rich dividers:
   ```python
   from rich.console import Group
   from rich.rule import Rule

   content = Group(
       Rule(f"Parallel Batch #{batch_id}", style=colors.secondary),
       tool_table,
       Text(f"Completed in {elapsed_ms}ms (~{speedup}x faster)", style=colors.muted)
   )
   ```

4. **Configuration option** to toggle between plain text and styled batch output

### Missing Context

- **User preference research**: Have users expressed preference for one style over another?
- **Performance benchmarks**: What is the rendering overhead of Rich panels vs plain text?
- **Accessibility considerations**: Does plain text provide better screen reader support?

## References

### Core Files

- [src/tunacode/core/agents/agent_components/node_processor.py](src/tunacode/core/agents/agent_components/node_processor.py) - Parallel batch execution and formatting
- [src/tunacode/core/agents/main.py](src/tunacode/core/agents/main.py) - Final batch formatting
- [src/tunacode/ui/panels.py](src/tunacode/ui/panels.py) - Rich panel implementations (agent, streaming)
- [src/tunacode/ui/output.py](src/tunacode/ui/output.py) - Core output functions (print, muted, logging wrappers)
- [src/tunacode/cli/repl.py](src/tunacode/cli/repl.py) - Formatting decision tree root
- [src/tunacode/cli/repl_components/output_display.py](src/tunacode/cli/repl_components/output_display.py) - Non-streaming display logic

### Supporting Files

- [src/tunacode/ui/tool_descriptions.py](src/tunacode/ui/tool_descriptions.py) - Batch description generation
- [src/tunacode/ui/console.py](src/tunacode/ui/console.py) - Rich console initialization
- [src/tunacode/ui/logging_compat.py](src/tunacode/ui/logging_compat.py) - Unified logging interface
- [src/tunacode/constants.py](src/tunacode/constants.py) - UI color definitions
- [src/tunacode/core/agents/agent_components/tool_executor.py](src/tunacode/core/agents/agent_components/tool_executor.py) - Parallel execution engine
- [src/tunacode/core/agents/agent_components/streaming.py](src/tunacode/core/agents/agent_components/streaming.py) - Token streaming callbacks

### Related Research

- [memory-bank/research/2025-11-17_16-49-12_parallel-tool-calling-single-batch-issue.md](memory-bank/research/2025-11-17_16-49-12_parallel-tool-calling-single-batch-issue.md) - Parallel tool calling behavior analysis

## Data Flow Summary

```
User Input
    │
    ├─→ REPL (repl.py:141-168)
    │   └─→ Decision: enable_streaming?
    │       ├─→ TRUE: Create StreamingAgentPanel
    │       │   └─→ Progressive Rich panel updates during agent execution
    │       │
    │       └─→ FALSE: Wait for completion
    │           └─→ Display via output_display.py
    │               └─→ ui.agent() → Rich panel with markdown
    │
    └─→ Tool Execution (node_processor.py:315-422)
        └─→ Batch read-only tools
            └─→ Display via ui.muted() → Plain text with separators
                ├─→ Batch header: "PARALLEL BATCH #{id}: Executing {count} tools..."
                ├─→ Tool list: "  [1] tool_name → args"
                └─→ Metrics: "Completed in {time}ms (~{speedup}x faster)"
```

## Architectural Decision Record

**Issue:** Tool execution output uses plain text formatting while agent responses use styled Rich panels, creating visual inconsistency.

**Context:** The codebase has two distinct output paths:
1. Agent responses → User-facing content → Rich panels with styling
2. Tool execution → System diagnostics → Plain text via `muted()` function

**Decision:** The separation is intentional architectural design, not a bug or oversight.

**Consequences:**
- **Positive:**
  - Clear visual hierarchy (agent content emphasized)
  - Faster rendering for diagnostic output
  - Simpler scanning of batch execution details

- **Negative:**
  - Visual inconsistency noted by users
  - Parallel batch output feels less polished
  - Lacks accessibility features of Rich panels (proper markup, screen reader support)

**Alternatives Considered:**
1. Unified Rich panel formatting for all output
2. Configuration toggle for styled vs plain diagnostics
3. Separate "verbose" mode with detailed Rich tables for tool execution

## Next Steps

To address the formatting inconsistency:

1. **Prototype batch panel function** in `ui/panels.py` using Rich Table or Panel
2. **Benchmark rendering performance** comparing plain text vs Rich panels for batch output
3. **Gather user feedback** on preferred batch output styling
4. **Consider accessibility** requirements for screen readers and terminal types
5. **Update CLAUDE.md** with architectural decision documentation if keeping separation intentional

## Additional Search Paths

For deeper investigation:

```bash
# Find all muted() usage
grep -r "ui.muted" src/tunacode/

# Find all agent() panel usage
grep -r "ui.agent" src/tunacode/

# Find Rich panel creation
grep -r "Panel(" src/tunacode/ui/

# Find batch formatting logic
grep -r "PARALLEL BATCH" src/tunacode/
grep -r "faster than sequential" src/tunacode/
```
