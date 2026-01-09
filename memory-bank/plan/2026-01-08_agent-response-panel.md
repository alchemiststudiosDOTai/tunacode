---
title: "Agent Response Panel – Plan"
phase: Plan
date: "2026-01-08"
owner: "Claude"
parent_research: "memory-bank/research/2026-01-08_agent-reply-rendering-analysis.md"
git_commit_at_plan: "9db8e92"
tags: [plan, ui, rendering, nextstep]
---

## Goal

Create a 3-zone panel renderer for agent text responses that matches the visual consistency of existing tool panels, following NeXTSTEP design principles.

**Non-goals:**
- ~~Streaming panel display (keep current streaming behavior)~~ **SUPERSEDED: Streaming panels implemented**
- User message panel treatment (future work)
- New test files (existing pattern, no new tests needed)

## Scope & Assumptions

**In scope:**
- New `AgentResponseRenderer` class following `BaseToolRenderer` pattern
- 3-zone layout: Header, Viewport, Status (no Params zone)
- Metrics display: tokens, duration, model name
- Integration at finalization point in `app.py`

**Out of scope:**
- ~~Streaming display changes~~ **SUPERSEDED: `render_agent_streaming()` implemented**
- User message styling
- New dependencies

**Assumptions:**
- `session.last_call_usage` contains tokens at finalization time
- `session.current_model` contains model name
- Duration can be tracked via simple timestamp delta

## Deliverables

1. `src/tunacode/ui/renderers/agent_response.py` - New renderer module
2. `src/tunacode/ui/app.py` - Integration at lines 307-310

## Readiness

**Preconditions met:**
- `BaseToolRenderer` pattern exists and is well-documented
- Token usage tracked in `SessionState.last_call_usage`
- Model name available via `state_manager.session.current_model`
- Panel constants available in `tunacode.constants`

## Design Decisions (NeXTSTEP-Informed)

### 1. Border Color: `accent` (pink/magenta)
**Rationale:** Matches the existing `"agent:"` label styling. NeXTSTEP principle: "Objects that look the same should act the same." The accent color already signals "this is agent output" - the panel should reinforce that.

### 2. Status Bar Metrics: All Three
**Content:** `{tokens}  ·  {duration}  ·  {model}`
**Rationale:** NeXTSTEP feedback principle: "User must always see result of their action." All three metrics answer natural user questions:
- How many tokens? (cost awareness)
- How long? (performance awareness)
- What model? (capability awareness)

### 3. Streaming: ~~Keep Current Behavior~~ **SUPERSEDED**
**Original Rationale:** Panel only on finalization. NeXTSTEP principle: "When in doubt, don't."
**Update:** Streaming panels were implemented via `render_agent_streaming()` with live elapsed time and model display. Provides consistent visual framing throughout the response lifecycle.

## Milestones

- **M1:** Create `AgentResponseRenderer` skeleton with 3-zone pattern
- **M2:** Wire up metrics (tokens, duration, model) to renderer
- **M3:** Integrate into `app.py` finalization flow
- **M4:** Verify visual consistency with tool panels

## Work Breakdown (Tasks)

### Task 1: Create AgentResponseRenderer Module
**Summary:** Create new renderer following existing pattern
**Owner:** Claude
**Dependencies:** None
**Target Milestone:** M1

**Files touched:**
- `src/tunacode/ui/renderers/agent_response.py` (new)

**Implementation:**
```python
# Simplified 3-zone renderer (Header, Viewport, Status - no Params)
# Follow BaseToolRenderer pattern but lighter weight
# No parse_result needed - just takes content + metrics directly
```

**Acceptance test:** Module imports without error, renders a test panel

---

### Task 2: Add Duration Tracking
**Summary:** Track request start time to calculate duration at finalization
**Owner:** Claude
**Dependencies:** Task 1
**Target Milestone:** M2

**Files touched:**
- `src/tunacode/ui/app.py` (modify `_process_request_queue`)

**Implementation:**
- Add `request_start_time = time.monotonic()` at request start
- Calculate `duration_ms = (time.monotonic() - request_start_time) * 1000` at finalization

**Acceptance test:** Duration displays correctly in status bar

---

### Task 3: Wire Metrics to Renderer
**Summary:** Pass tokens, duration, model to renderer at finalization
**Owner:** Claude
**Dependencies:** Task 1, Task 2
**Target Milestone:** M2

**Files touched:**
- `src/tunacode/ui/app.py` (finalization block at lines 307-310)

**Implementation:**
```python
# Get metrics from state_manager
tokens = state_manager.session.last_call_usage.get("completion_tokens", 0)
model = state_manager.session.current_model
duration_ms = calculated_duration
```

**Acceptance test:** All three metrics appear in rendered panel

---

### Task 4: Replace Raw Output with Panel
**Summary:** Replace `app.py:307-310` raw Markdown with renderer call
**Owner:** Claude
**Dependencies:** Task 1, Task 2, Task 3
**Target Milestone:** M3

**Files touched:**
- `src/tunacode/ui/app.py` (lines 307-310)

**Current code:**
```python
if self.current_stream_text and not self._streaming_cancelled:
    self.rich_log.write("")
    self.rich_log.write(Text("agent:", style="accent"))
    self.rich_log.write(Markdown(self.current_stream_text))
```

**New code:**
```python
if self.current_stream_text and not self._streaming_cancelled:
    from tunacode.ui.renderers.agent_response import render_agent_response
    panel = render_agent_response(
        content=self.current_stream_text,
        tokens=self.state_manager.session.last_call_usage.get("completion_tokens", 0),
        duration_ms=duration_ms,
        model=self.state_manager.session.current_model,
    )
    self.rich_log.write(panel)
```

**Acceptance test:** Agent responses display in styled panels matching tool panel aesthetics

---

### Task 5: Visual Verification
**Summary:** Manually verify panel appearance matches tool panels
**Owner:** Claude
**Dependencies:** Task 4
**Target Milestone:** M4

**Verification checklist:**
- [ ] Border color is accent (pink/magenta)
- [ ] Header shows "agent" title with timestamp
- [ ] Viewport contains properly rendered Markdown
- [ ] Status bar shows tokens, duration, model
- [ ] Panel width matches TOOL_PANEL_WIDTH constant
- [ ] Separators use consistent BOX_HORIZONTAL character

**Acceptance test:** Visual inspection confirms NeXTSTEP consistency

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Token count not available at finalization | Low | Medium | Fall back to estimated tokens via `estimate_tokens()` |
| Duration tracking interferes with async flow | Low | Low | Use monotonic clock, isolated variable |
| Panel too wide for terminal | Low | Low | Existing TOOL_PANEL_WIDTH handles this |

## Test Strategy

No new test files. The pattern follows existing `BaseToolRenderer` which has established behavior. Manual verification in Task 5 confirms visual correctness.

## References

- Research: `memory-bank/research/2026-01-08_agent-reply-rendering-analysis.md`
- BaseToolRenderer pattern: `src/tunacode/ui/renderers/tools/base.py:245-443`
- Current finalization: `src/tunacode/ui/app.py:307-310`
- NeXTSTEP skill: `.claude/skills/neXTSTEP-ui/SKILL.md`
- Token tracking: `src/tunacode/core/agents/agent_components/node_processor.py:129-153`

## Final Gate

**Plan output:** `memory-bank/plan/2026-01-08_agent-response-panel.md`
**Milestone count:** 4
**Task count:** 5
**Ready for coding:** Yes

**Next command:** Execute this plan to implement the agent response panel.
