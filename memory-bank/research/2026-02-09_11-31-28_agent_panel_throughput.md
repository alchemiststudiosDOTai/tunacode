# Research -- Agent Panel Missing t/s (Throughput) Display

**Date:** 2026-02-09
**Owner:** agent
**Phase:** Research

## Goal

Map out why the agent panel no longer displays tokens-per-second (`t/s`) after the unified CSS panel migration (PR #373) and the tinyAgent migration (PR #374). Determine root cause and identify all files in the fix path.

## Findings

### The Rendering Logic Is Intact

The `render_agent_response` function correctly computes and formats throughput:

- `src/tunacode/ui/renderers/agent_response.py:141-142` -- Guard requires both `tokens > 0` and `duration_ms > 0`:
  ```python
  if tokens > 0 and duration_ms > 0:
      status_parts.append(f"{tokens * 1000 / duration_ms:.0f} t/s")
  ```
- The status bar, separator, and layout are all structurally correct.
- CSS classes (`agent-panel`) are applied properly via `PanelMeta`.

### The Single Call Site Passes Zero Tokens

- `src/tunacode/ui/app.py:229-230` -- reads tokens from state:
  ```python
  session = self.state_manager.session
  tokens = session.usage.last_call_usage.completion_tokens  # Always 0
  ```
- `duration_ms` at line 228 IS valid (wall-clock timer set at line 187).
- Since `tokens == 0`, the guard at `agent_response.py:141` never fires.

### Root Cause: Usage Write-Side Is Missing

The pipeline from API response to `UsageMetrics` is **completely disconnected**:

| Layer | Status | File |
|-------|--------|------|
| `UsageMetrics` dataclass | Defined, correct | `src/tunacode/types/canonical.py:183-224` |
| `UsageState` container | Defined, correct | `src/tunacode/core/types/state_structures.py:59-64` |
| `session.usage.last_call_usage` | Read by UI at `app.py:230` | Never written to |
| `session.usage.session_total_usage` | Persisted on save/load | Never accumulated |
| tinyagent `AssistantMessage.usage` field | Field exists | Never populated by provider |
| OpenRouter SSE stream final chunk | Contains `usage` data | Not extracted by provider |
| `RequestOrchestrator` event handlers | Handle 6 event types | None extract usage |

### The Broken Pipeline (Data Flow)

```
OpenRouter API returns usage on final SSE chunk
  |
  X -- tinyagent openrouter_provider.py:303-326 does NOT extract `usage` from chunks
  |
  X -- AssistantMessage.usage (agent_types.py:128) is always None
  |
  X -- RequestOrchestrator._handle_stream_message_end (main.py:331) ignores usage
  |
  X -- No code writes to session.usage.last_call_usage
  |
  app.py:230 reads completion_tokens => 0
  |
  agent_response.py:141 guard fails => no t/s displayed
```

### Before vs After the Migrations

- **Before (pydantic-ai era):** pydantic-ai tracked usage natively. The `last_call_usage` was populated after each call, so `t/s` displayed correctly.
- **After (tinyAgent migration, PR #374):** tinyAgent has zero usage tracking. The read-side infrastructure (`UsageMetrics`, `UsageState`, the UI consumer) survived the migration. The write-side did not.
- **PR #373 (CSS panel migration):** Changed `render_agent_response` to return `(content, PanelMeta)` instead of a Rich `Panel`. This did NOT break `t/s` -- the throughput calculation logic was preserved verbatim. The issue is purely data, not rendering.

### Relevant Files & Why They Matter

| File | Role |
|------|------|
| `src/tunacode/ui/renderers/agent_response.py` | Renders t/s in status bar (line 141-142). Logic is correct. |
| `src/tunacode/ui/app.py` | Reads `completion_tokens` at line 230, passes to renderer at line 232. |
| `src/tunacode/core/agents/main.py` | `RequestOrchestrator` handles stream events (lines 298-427). Missing usage extraction. |
| `src/tunacode/core/types/state_structures.py` | `UsageState` with `last_call_usage` and `session_total_usage` (lines 59-64). |
| `src/tunacode/types/canonical.py` | `UsageMetrics` dataclass (lines 183-224). |
| `src/tunacode/core/tinyagent/__init__.py` | Local tinyagent wrapper. Potential place to intercept usage. |
| `.venv/.../tinyagent/openrouter_provider.py` | SSE parser at lines 303-326. Does not extract `usage` from final chunk. |
| `.venv/.../tinyagent/agent_types.py` | `AssistantMessage` has `usage: JsonObject \| None` at line 128 (never set). |

### Secondary Finding: `render_agent_streaming` Is Dead Code

- Defined at `agent_response.py:61-109`
- Zero production call sites (only called in test file)
- Was part of the streaming UI before the refactor

## Key Patterns / Solutions Found

- **Two-point fix:** The fix needs changes at two points:
  1. **tinyagent provider level** -- Extract `usage` from the final SSE chunk in the OpenRouter provider (or in a local wrapper/middleware)
  2. **RequestOrchestrator level** -- Read usage from the `message_end` or `agent_end` event and write it to `session.usage.last_call_usage`

- **Alternative single-point fix:** If modifying tinyagent's provider is undesirable, the `_handle_stream_agent_end` handler at `main.py:416` could inspect the persisted messages for a usage field, or the agent object itself could expose usage after completion.

- **Duration is already working:** The `duration_ms` path is functional. Only `tokens` (completion_tokens) is missing.

## Knowledge Gaps

- Whether tinyagent's `Agent` object exposes usage data post-completion (e.g., `agent.last_usage` or similar)
- Whether OpenRouter's SSE stream reliably includes `usage` on the final chunk for all models
- Whether tinyagent has plans to add native usage tracking (upstream fix vs. local patch)
- Whether `render_agent_streaming` should be deleted or reconnected for live streaming panels

## References

- `src/tunacode/ui/renderers/agent_response.py` -- Throughput rendering logic
- `src/tunacode/ui/app.py` -- Call site and timer logic
- `src/tunacode/core/agents/main.py` -- Stream event handlers
- `src/tunacode/types/canonical.py` -- `UsageMetrics` definition
- `src/tunacode/core/types/state_structures.py` -- `UsageState` definition
- `memory-bank/research/2026-01-27_16-11-11_streaming_and_panels.md` -- Prior streaming/panel research
- `memory-bank/research/2026-01-27_17-45-00_chatcontainer_refactor.md` -- Chat container refactor research
