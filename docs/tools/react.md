---
title: React Tool
link: docs-tools-react
type: doc
path: docs/tools/react.md
depth: 2
seams: [D, M]
ontological_relations:
  - relates_to: [[Agent State]], [[Tools Overview]], [[ReAct Pattern]], [[State Management]]
  - affects: [[Agent Behavior]], [[Session Persistence]]
  - uses: [[StateManagerProtocol]]
tags:
  - react
  - ReAct-pattern
  - scratchpad
  - agent-memory
  - working-memory
  - planning
  - reasoning
  - cognitive-aid
  - workflow
  - persistence
  - timeline
  - chronological-tracking
  - think-observe-cycle
  - multi-step
  - complex-tasks
  - iterative-problem-solving
  - session-state
  - state-management
  - factory-pattern
  - async-tool
  - JSON-serialization
  - debugging-workflow
  - refactoring-workflow
  - tool-execution-tracking
  - contextual-reasoning
  - hypothesis-tracking
  - process-transparency
  - agent-introspection
created_at: 2026-01-09T14:03:10.288152
updated_at: 2026-01-09T14:03:10.288152
uuid: 550e8400-e29b-41d4-a716-446655440000
---

# React Tool

## Purpose
A lightweight agent scratchpad for tracking ReAct-style reasoning during complex workflows. Maintains persistent memory across tool invocations to support context in multi-step problem-solving and debugging.

## Overview
The React tool provides a timeline-based scratchpad that stores entries for "think" (reasoning, planning) and "observe" (results, findings), enabling agents and users to review and persist their reasoning and observations over time.

- **Design**: Uses a persistent timeline in agent session state via `StateManager.react_scratchpad` (with JSON serialization).
- **Pattern**: Implements the [ReAct Pattern](https://arxiv.org/abs/2210.03629) (reasoning and acting in alternation) for better transparency and planning.

## Core Actions
The react tool provides four primary async actions:

### think
Records reasoning, thoughts, or analysis, plus a planned next action.

**Parameters:**
- `thoughts: str`: Current thinking or key notes
- `next_action: str`: Intended next step or action

**Example:**
```javascript
react({
  action: "think",
  thoughts: "Investigate the authentication logic",
  next_action: "read_file src/auth.py"
})
```

### observe
Captures results or observations after tool execution.

**Parameters:**
- `result: str`: Observed result or finding

**Example:**
```javascript
react({
  action: "observe",
  result: "Found 3 auth functions in src/auth.py, confirming dependencies"
})
```

### get
Fetches the formatted history (timeline) of all steps.
- **Returns:** Numbered list of recorded "think" and "observe" steps
- **Format:**
  ```
  1. think: thoughts='...', next_action='...'
  2. observe: result='...'
  ```

### clear
Resets the scratchpad to empty, clearing all timeline entries.

## State Integration
- All entries persist in `SessionState.react_scratchpad`:
  ```json
  {
    "timeline": [
      {"type": "think", "thoughts": "...", "next_action": "..."},
      {"type": "observe", "result": "..."}
    ]
  }
  ```
- The timeline is automatically saved and loaded with each session for continuity and reproducibility.

## Implementation Details
- Factory: `create_react_tool(state_manager)` binds the tool to agent/session state
- Each action (think, observe, get, clear) maps to a command param, validated and logged
- Timeline items are fully JSON-serializable for transport, save/load

## Advanced Features & Best Practices
- Track your investigation and analysis process step-by-step
- Use "think" for every hypothesis, checkpoint, or planned next tool call
- Use "observe" to capture every non-trivial output, intermediate result, or insight gained
- Clear the scratchpad at the start of major new workflows for clarity
- Use timeline output as an agent audit trail for debugging or approval
- See [Tools Architecture](../tools/architecture.md) and [Tools Overview](../codebase-map/modules/tools-overview.md) for more on how agent tools are structured and invoked

## Backwards Compatibility
- Legacy wrapper: `ReactTool` class exposes `execute()` for pre-factory code:
```python
tool = ReactTool(state_manager)
result = await tool.execute(
   action="think",
   thoughts="reasoning",
   next_action="next step"
)
```

## Use Cases
- **Complex Refactoring**: Multi-phase code change and confirmation flows
- **Debug Investigation**: Multi-hop exploration or hypothesis tracking
- **Agent Transparency**: Auditable record of what the agent "thought" and "learned"
- **Iterative/Collaborative Planning**: Capture process for reviewers or future automation

## Related and Implementation Files
- Implementation: `src/tunacode/tools/react.py`
- State management: `src/tunacode/core/state.py` (`SessionState.react_scratchpad`)
- See also: `docs/tools/architecture.md`, `docs/codebase-map/modules/tools-overview.md`
