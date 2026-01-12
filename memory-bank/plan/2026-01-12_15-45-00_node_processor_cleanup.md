---
title: "node_processor.py Replacement – Plan"
phase: Plan
date: "2026-01-12T15:45:00Z"
owner: "agent"
parent_research: "memory-bank/research/2026-01-12_15-30-07_node_processor_mapping.md"
git_commit_at_plan: "642830f"
tags: [plan, node_processor, rewrite, coding]
---

## Goal

- DELETE `node_processor.py` entirely and replace with 4 focused single-purpose modules.

### Non-Goals

- No salvaging the existing mess
- No deployment or ops changes
- No changes to external API (`main.py:403` still calls same function signature)

## Scope & Assumptions

### In Scope

- DELETE `node_processor.py` (486 lines of tangled code)
- CREATE 4 new focused modules from scratch
- CREATE thin orchestrator to compose them
- Single caller (`main.py:403`) continues to work unchanged

### Out of Scope

- Changing the ResponseState state machine
- Modifying tool execution strategy
- Altering callback signatures

### Assumptions

- Python 3.11+ with current pydantic-ai version
- No concurrent work on this module

## Deliverables

1. `message_recorder.py` - Append messages to session
2. `usage_tracker.py` - Token/cost accounting
3. `completion_detector.py` - Marker and truncation detection
4. `tool_dispatcher.py` - Categorize, batch, execute tools
5. `node_orchestrator.py` - Thin orchestrator composing the above (replaces node_processor.py)
6. DELETE `node_processor.py`

## Readiness

### Preconditions

- [x] Research complete
- [x] Git clean on branch: `node-processor-cleanup`
- [x] Current commit: `642830f`

## Milestones

| Milestone | Description | Exit Criteria |
|-----------|-------------|---------------|
| M1 | Create `message_recorder.py` | Clean module, functions work |
| M2 | Create `usage_tracker.py` | Token tracking works |
| M3 | Create `completion_detector.py` | Detection works |
| M4 | Create `tool_dispatcher.py` | Tool execution works |
| M5 | Create `node_orchestrator.py`, DELETE `node_processor.py` | Agent loop works |

## Work Breakdown (Tasks)

### Task 1: Create `message_recorder.py`

**Summary:** Fresh module for message appending

**Target Milestone:** M1

**Files:**

- CREATE: `src/tunacode/core/agents/agent_components/message_recorder.py`

**Interface:**

```python
def record_request(session: Session, request: Any) -> None: ...
def record_thought(session: Session, thought: Any) -> None: ...
def record_model_response(session: Session, response: Any) -> None: ...
```

**Acceptance:** Functions append to `session.messages` correctly

---

### Task 2: Create `usage_tracker.py`

**Summary:** Fresh module for token/cost tracking

**Target Milestone:** M2

**Files:**

- CREATE: `src/tunacode/core/agents/agent_components/usage_tracker.py`

**Interface:**

```python
def update_usage(session: Session, usage: Usage, model_name: str) -> None: ...
```

**Acceptance:** Token counts and cost accumulate correctly

---

### Task 3: Create `completion_detector.py`

**Summary:** Fresh module for completion/truncation detection

**Target Milestone:** M3

**Files:**

- CREATE: `src/tunacode/core/agents/agent_components/completion_detector.py`

**Interface:**

```python
def detect_completion(text: str, has_tool_calls: bool) -> CompletionResult: ...
def detect_truncation(text: str) -> bool: ...
def has_premature_intention(text: str) -> bool: ...
```

**Acceptance:** Known markers detected correctly

---

### Task 4: Create `tool_dispatcher.py`

**Summary:** Fresh module for tool categorization, batching, execution

**Target Milestone:** M4

**Files:**

- CREATE: `src/tunacode/core/agents/agent_components/tool_dispatcher.py`

**Interface:**

```python
async def dispatch_tools(
    parts: list[Part],
    state_manager: StateManager,
    tool_callback: ToolCallback,
    tool_result_callback: ToolResultCallback,
    tool_start_callback: ToolStartCallback,
) -> ToolDispatchResult: ...
```

**Acceptance:** Correct batching order (research → read-only parallel → write sequential)

---

### Task 5: Create `node_orchestrator.py`, DELETE `node_processor.py`

**Summary:** Thin orchestrator + delete the mess

**Target Milestone:** M5

**Files:**

- CREATE: `src/tunacode/core/agents/agent_components/node_orchestrator.py`
- DELETE: `src/tunacode/core/agents/agent_components/node_processor.py`
- MODIFY: `src/tunacode/core/agents/agent_components/__init__.py`
- MODIFY: `src/tunacode/core/agents/main.py` (update import)

**Signature (unchanged for caller):**

```python
async def process_node(
    node: AgentNode,
    state_manager: StateManager,
    tool_buffer: ToolBuffer,
    tool_callback: ToolCallback,
    streaming_callback: StreamingCallback,
    tool_result_callback: ToolResultCallback,
    tool_start_callback: ToolStartCallback,
) -> tuple[bool, str | None]: ...
```

**Acceptance:** `main.py` agent loop works, `ruff check .` passes

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Miss edge case behavior | Medium | Reference research doc data flow diagram |
| Import cycles | Low | New modules only import types/utils |

## Test Strategy

- Manual agent loop test after M5
- Run existing tests if any

## References

- Research: `memory-bank/research/2026-01-12_15-30-07_node_processor_mapping.md`
- Data flow diagram: Research doc lines 159-212

## Final Gate

| Check | Value |
|-------|-------|
| Plan path | `memory-bank/plan/2026-01-12_15-45-00_node_processor_cleanup.md` |
| Milestones | 5 |
| Tasks | 5 |
| Ready for coding | Yes |

**Next command:** `/ce:ex "memory-bank/plan/2026-01-12_15-45-00_node_processor_cleanup.md"`
