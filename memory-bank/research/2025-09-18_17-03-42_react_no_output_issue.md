# Research – ReAct Feedback Loop "No Output" Issue Investigation

**Date:** 2025-09-18 17:03:42 UTC
**Owner:** context-engineer:research
**Phase:** Research

## Goal
Investigate why the ReAct feedback loop shows "no output" in the first two steps despite recent implementation updates.

## Methodology
- Analyzed ReactCoordinator implementation and output flow
- Examined planner and evaluator agent configuration and prompts
- Investigated state management and process_request integration
- Studied feedback loop integration and iteration handling

## Additional Search
- `grep -ri "no output" .claude/` - No existing research on this specific issue
- `grep -ri "react" .claude/` - Found documentation about ReAct components

## Findings

### Relevant Files & Purpose
- `src/tunacode/core/agents/main.py:220-404` → ReactCoordinator class implementation
- `src/tunacode/core/agents/main.py:666-679` → ReactCoordinator initialization and bootstrap
- `src/tunacode/core/agents/main.py:766-777` → Per-iteration observation and feedback integration
- `src/tunacode/core/agents/agent_components/agent_config.py:56-103` → ReAct agent configuration and caching
- `.claude/semantic_index/intent_mappings.json` → ReAct component relationships

### Root Cause Analysis

#### 1. **Silent Operation by Design**
ReAct agents operate as background helpers:
- Agent responses are processed internally and never displayed directly
- Only formatted messages are injected into conversation history
- Raw agent responses are hidden from user view

#### 2. **Early Iteration Timing Issues**
- Bootstrap happens BEFORE main agent starts, creating initial plan based only on query
- First two observations likely empty (`_node_output_text()` returns empty string)
- ReAct messages added AFTER main agent response processing

#### 3. **Message Visibility Constraints**
- ReAct thoughts only visible when `show_thoughts=True` (defaults to `False`)
- Messages use muted UI color (#94a3b8) making them less prominent
- Early iterations may produce minimal/no actionable feedback

#### 4. **State Synchronization Problems**
- ReactCoordinator calls happen after `_process_node()` completion
- Race condition with `response_state.task_completed` signals
- Empty response handling interferes with feedback timing

### Key Implementation Details

#### ReactCoordinator Message Flow:
```
Agent Call → JSON Parsing → Message Formatting → create_user_message() → Session History
```

#### Integration Points in process_request():
1. **Line 676**: `await react_coordinator.bootstrap(message)` - Initial plan generation
2. **Line 767**: `observation_text = _node_output_text(node)` - Observation extraction
3. **Line 777**: `await react_coordinator.observe_step()` - Feedback generation

#### Configuration Constants:
- `REACT_MAX_STEPS = 4` - Maximum planner/evaluator cycles
- `UNPRODUCTIVE_LIMIT = 3` - Iterations without tool use before forcing action
- `show_thoughts: bool = False` - Controls thought visibility

## Key Patterns / Solutions Found

### **Silent Observer Pattern**: ReAct agents process information silently, only injecting formatted guidance messages into conversation history.

### **Conditional Display Logic**: Messages are only visible through:
- Injected conversation messages (always visible)
- Thought logging (when enabled)
- Primary agent behavior changes

### **Graceful Degradation**: System continues base functionality when ReAct components fail.

### **State-Aware Integration**: ReactCoordinator respects main agent completion signals and iteration limits.

## Knowledge Gaps

- Exact UI rendering behavior for early iteration messages
- Whether bootstrap messages are being displayed properly
- How `_node_output_text()` handles different node types in early iterations
- Impact of agent response timing on feedback visibility
- Performance characteristics of message injection pattern

## Potential Solutions

1. **Enhanced Early Iteration Handling**: Improve observation extraction for empty/minimal output
2. **Bootstrap Message Visibility**: Ensure initial plan is properly displayed
3. **Message Timing Optimization**: Adjust when ReAct messages are injected relative to main agent processing
4. **Debug Visibility**: Add optional verbose logging for ReAct operation during development

## References

### Code References
- ReactCoordinator: `src/tunacode/core/agents/main.py:220-404`
- Integration: `src/tunacode/core/agents/main.py:666-679,766-777`
- Agent Config: `src/tunacode/core/agents/agent_components/agent_config.py:56-103`

### GitHub Permalinks
- [ReactCoordinator implementation](https://github.com/alchemiststudiosDOTai/tunacode/blob/245b7c4953c29512ced3a40bebca03f0090cded3/src/tunacode/core/agents/main.py#L220-404)
- [process_request integration](https://github.com/alchemiststudiosDOTai/tunacode/blob/245b7c4953c29512ced3a40bebca03f0090cded3/src/tunacode/core/agents/main.py#L666-679)
- [Agent configuration](https://github.com/alchemiststudiosDOTai/tunacode/blob/245b7c4953c29512ced3a40bebca03f0090cded3/src/tunacode/core/agents/agent_components/agent_config.py#L56-103)

### Documentation
- [ReAct Component Overview](https://github.com/alchemiststudiosDOTai/tunacode/blob/245b7c4953c29512ced3a40bebca03f0090cded3/.claude/docs_model_friendly/component_purpose.md)
- [Memory Anchor](https://github.com/alchemiststudiosDOTai/tunacode/blob/245b7c4953c29512ced3a40bebca03f0090cded3/.claude/memory_anchors/react_shim_anchor.md)
- [Intent Mappings](https://github.com/alchemiststudiosDOTai/tunacode/blob/245b7c4953c29512ced3a40bebca03f0090cded3/.claude/semantic_index/intent_mappings.json)

## ReAct Feedback Loop Enhancement Plan

### Goal

Improve the ReAct feedback loop to eliminate "no output" noise while ensuring the agent doesn't get stuck without guidance.

### Changes

#### 1. Add Smart Threshold Logic

Replace the current simple filter with intelligent threshold-based evaluation:

```python
# Only evaluate when we have meaningful output OR after too many empty iterations
if not observation.strip():
    # Track consecutive empty observations
    self._snapshot.consecutive_empty += 1
    if self._snapshot.consecutive_empty <= 2:  # Skip first 2 empty observations
        return
    # After 3+ empty observations, provide guidance anyway
```

#### 2. Enhance ReactLoopSnapshot

Add tracking for consecutive empty observations:

```python
@dataclass(slots=True)
class ReactLoopSnapshot:
    step_index: int = 0
    consecutive_empty: int = 0  # Track empty observation streak
    last_feedback: Optional[str] = None
    last_plan: Optional[str] = None
    enabled: bool = True
```

#### 3. Update Evaluator Prompt Logic

Maintain the current note but add handling for forced evaluations:

```python
def _build_evaluator_prompt(self, query: str, observation: str) -> str:
    plan = self._snapshot.last_plan or "No explicit plan recorded"
    # Handle forced evaluations due to empty streak
    obs_text = observation if observation.strip() else "Agent has not produced observable output for several iterations"
```

#### 4. Reset Counter on Success

Reset the empty counter when meaningful output is detected:

```python
if observation.strip():
    self._snapshot.consecutive_empty = 0  # Reset counter on meaningful output
```

### Benefits

- ✅ Eliminates early "no output" noise (iterations 1-2)
- ✅ Provides guidance if agent is stuck (iteration 3+)
- ✅ Prevents infinite reasoning loops
- ✅ Maintains clean operation for normal cases
- ✅ Backwards compatible - no breaking changes

### Testing Strategy

1. Test with simple queries (should be quiet initially)
2. Test with complex queries (should provide guidance when stuck)
3. Test edge cases where agent produces no output
4. Verify existing functionality remains intact

---
**Git Commit:** 245b7c4953c29512ced3a40bebca03f0090cded3
**Research ID:** react-no-output-investigation-001
