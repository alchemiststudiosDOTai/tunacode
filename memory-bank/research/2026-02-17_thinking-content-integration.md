# Research - ThinkingContent Integration for Reasoning Models

**Date:** 2026-02-17
**Owner:** agent
**Phase:** Research

## Goal

Research how to integrate tinyAgent v1.2.0's `ThinkingContent` type and reasoning effort levels into tunacode's TUI. The goal is to cleanly separate reasoning/chain-of-thought from final response text, improving display for reasoning models like DeepSeek R1.

## Findings

### tinyAgent v1.2.0 API (New Features)

| Component | Location | Description |
|-----------|----------|-------------|
| `ThinkingContent` | `tinyAgent/tinyagent/agent_types.py:86-92` | TypedDict with `type: "thinking"`, `thinking: str`, `cache_control` |
| `ThinkingLevel` enum | `tinyAgent/tinyagent/agent_types.py:52-60` | OFF, MINIMAL, LOW, MEDIUM, HIGH, XHIGH |
| `ReasoningMode` | `tinyAgent/tinyagent/alchemy_provider.py:38-39` | `bool | Literal["minimal","low","medium","high","xhigh"]` |
| `OpenAICompatModel.reasoning` | `tinyAgent/tinyagent/alchemy_provider.py:130` | Field to enable reasoning mode |
| Streaming events | `tinyAgent/tinyagent/agent_types.py:270-283` | `thinking_start`, `thinking_delta`, `thinking_end` |
| Example | `tinyAgent/examples/example_reasoning.py:34-51` | Block separation pattern with type guards |

**Key Pattern - Type Guards:**
```python
def is_thinking_content(block: AssistantContent | None) -> TypeGuard[ThinkingContent]:
    return block is not None and block.get("type") == "thinking"
```

**Block Separation:**
```python
content = message.get("content") or []
thinking_blocks = [b for b in content if is_thinking_content(b)]
text_blocks = [b for b in content if is_text_content(b)]
```

### Current Tunacode State

| Component | File | Status |
|-----------|------|--------|
| Stream handler | `src/tunacode/core/agents/main.py:521-536` | Only processes `text_delta`, ignores `thinking_delta` |
| Canonical types | `src/tunacode/types/canonical.py:51-56` | `ThoughtPart` already exists |
| Message adapter | `src/tunacode/utils/messaging/adapter.py:140-142,232-233` | ThinkingContent conversion exists |
| Session state | `src/tunacode/core/session/state.py:39` | `show_thoughts: bool = False` exists |
| Conversation state | `src/tunacode/core/types/state_structures.py:31` | `thoughts: list[str]` exists but never populated |
| UI rendering | `src/tunacode/ui/renderers/` | No thinking renderer exists |

**Critical Gap:** Line 527-528 in `main.py`:
```python
if assistant_event.get("type") != "text_delta":
    return  # <-- thinking_delta silently dropped!
```

### UI Patterns Available

| Pattern | Location | Description |
|---------|----------|-------------|
| Zone layout | `renderers/agent_response.py` | viewport + separator + status zones |
| PanelMeta | `widgets/chat.py:149` | Dataclass for CSS class, border titles |
| Panel types | `renderers/panels.py` | TOOL, ERROR, SEARCH, INFO, SUCCESS, WARNING |
| Styling | `styles/panels.tcss` | `.agent-panel`, `.tool-panel`, etc. |
| Colors | `constants.py:72` | `muted: #808080` suitable for thinking |

## Key Patterns / Solutions Found

1. **Event-driven streaming**: tinyAgent emits typed events with `thinking_start/delta/end` - tunacode just needs to handle them
2. **Canonical type exists**: `ThoughtPart` already in type system, adapter conversion works
3. **Panel metadata pattern**: Return `tuple[RenderableType, PanelMeta]` for styled content
4. **Collapsible sections**: Could use Rich `Collapsible` or custom widget with `.thinking-panel` CSS

## Integration Plan

### Phase 1: Stream Event Handling

**File:** `src/tunacode/core/agents/main.py`

1. Add `thinking_callback` parameter to `RequestOrchestrator`
2. Modify `_handle_message_update()` to handle `thinking_delta`:
```python
ev_type = assistant_event.get("type")
if ev_type == "text_delta":
    # existing code
elif ev_type == "thinking_delta" and self.thinking_callback:
    delta = assistant_event.get("delta")
    if delta:
        await self.thinking_callback(delta)
```

### Phase 2: UI Display

**New file:** `src/tunacode/ui/renderers/thinking.py`

```python
def render_thinking(content: str, collapsed: bool = True) -> tuple[RenderableType, PanelMeta]:
    """Render thinking/reasoning content with subdued styling."""
    meta = PanelMeta(
        css_class="thinking-panel",
        border_title="[#808080]reasoning[/]",
    )
    # Either collapsed or truncated display
    ...
```

**CSS:** `src/tunacode/ui/styles/panels.tcss`
```css
.thinking-panel {
    outline: solid $muted;
    padding: 0 1;
}
```

### Phase 3: App Integration

**File:** `src/tunacode/ui/app.py`

1. Add `#thinking-output` widget (collapsible Static)
2. Add `_thinking_callback()` method
3. Wire to `process_request()` call

### Phase 4: Model Configuration

**File:** `src/tunacode/configuration/models_registry.json`

Add `reasoning` field to DeepSeek/Kimi models:
```json
{
  "id": "deepseek/deepseek-r1",
  "reasoning": true
}
```

## Knowledge Gaps

1. **Reasoning effort levels**: How should user configure low/medium/high? Config setting or per-request?
2. **Thinking display**: Collapsed by default? Expandable? Or just truncated?
3. **Token counting**: Should thinking tokens count toward context display?
4. **History**: Should thinking be persisted in session or ephemeral?

## References

- tinyAgent v1.2.0 release: https://pypi.org/project/tiny-agent-os/1.2.0/
- tinyAgent GitHub: https://github.com/alchemiststudiosDOTai/tinyAgent/releases/tag/v1.2.0
- Example reasoning code: `tinyAgent/examples/example_reasoning.py`
- Tunacode streaming: `src/tunacode/core/agents/main.py:473-536`
- Canonical types: `src/tunacode/types/canonical.py:51-56`
- Panel system: `src/tunacode/ui/renderers/panels.py`
