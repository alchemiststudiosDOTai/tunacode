# Simplified Agent Implementation – Plan

**Phase:** Plan (Updated)
**Date:** 2025-09-29T11:15:30 (Updated: 2025-09-29)
**Owner:** context-engineer:plan
**Parent Research:** memory-bank/research/2025-09-29_11-08-14_state_and_task_logic.md
**Git Commit At Plan:** 6b6e6d5
**Tags:** [plan, simplification, agent-refactoring, completion-detection-fix]

## Goal
Create a simplified agent implementation inspired by TypeScript patterns, reducing the current 190+ line complex `process_request()` function to a ~40 line version while **FIXING PREMATURE COMPLETION PROBLEMS**. The current system causes agents to stop with "TUNACODE DONE" before fully addressing user needs, requiring users to ask again. **WE MUST FOCUS ON EXECUTION** and deliver a working simplified version that demonstrates natural completion detection.

## Problem Statement (Updated)
**Current Issue:** Agent completion detection is broken - agents stop prematurely with "TUNACODE DONE" markers before fully completing tasks, forcing users to ask again. This is caused by:
- Complex state machine with 7 patterns causing false completion signals
- Artificial "TUNACODE DONE" markers triggering too early
- Productivity tracking forcing premature stops
- Multiple competing completion detection mechanisms

**Target Solution:** TypeScript-inspired simple loop:
```python
while True:
    # 1. Process AI response
    # 2. Execute any tool calls
    # 3. Continue if tool calls were made (AI wants to keep working)
    # 4. Stop if no tool calls (AI naturally finished)
```

## Scope & Assumptions

### In Scope (Updated)
- **Fix completion detection**: Replace complex patterns with simple tool-call-based logic
- Implement `process_request_simple()` function alongside existing complex version
- **Remove artificial completion markers**: No more "TUNACODE DONE" forced stops
- Remove productivity tracking and forced actions that interrupt natural flow
- Maintain core streaming and tool execution functionality
- Create parallel execution path for testing and comparison
- **Validate completion detection works correctly** in real scenarios

### Out of Scope
- Removing existing complex implementation (preserve for compatibility)
- Advanced error recovery mechanisms (keep basic error handling)
- Complex buffering optimizations
- Performance benchmarking (basic spot-check only)
- Breaking existing API contracts

### Assumptions (Updated)
- **Natural completion works better**: AI stopping naturally (no tool calls) is more reliable than forced markers
- Current agent interface (`ac.get_or_create_agent`) remains stable
- Tool callback mechanism works as expected
- Streaming is optional and can be preserved
- Simple boolean conditions can replace complex state machine for completion detection

## Deliverables (DoD)

1. **`process_request_simple()` function** in `src/tunacode/core/agents/main.py`
   - Accepts same parameters as current function
   - Returns compatible `AgentRun` object
   - Implements simplified while loop with tool-call detection
   - ~40 lines of code maximum

2. **`_execute_node_tools()` helper function**
   - Handles tool execution from agent nodes
   - Returns boolean indicating if tools were executed
   - Preserves error handling but simplified

3. **Test validation**
   - Single comprehensive test comparing simple vs complex version outputs
   - Validates both produce equivalent results for basic scenarios

4. **Documentation**
   - Brief comment explaining simplification approach
   - Comparison table in code comments showing before/after complexity

## Readiness (DoR)

### Preconditions
- ✅ Git repository accessible at commit 6b6e6d5
- ✅ Existing complex implementation available for reference
- ✅ Research document identifies 7 complex patterns to simplify
- ✅ TypeScript patterns identified from codebase search

### Data/Access
- ✅ Full read access to `src/tunacode/core/agents/main.py:416-605`
- ✅ Access to agent component files for interface understanding
- ✅ Test framework available (`hatch run test`)

### Environment
- ✅ Python environment with `.venv` and `uv` package management
- ✅ Existing test suite can be extended

## Milestones

### M1: Architecture & Skeleton (Day 1)
- [ ] Create `process_request_simple()` function signature
- [ ] Implement basic while loop structure
- [ ] Add `_execute_node_tools()` helper
- [ ] Verify function compiles

### M2: Core Feature Implementation (Day 1)
- [ ] Implement tool execution logic
- [ ] Add streaming callback support
- [ ] Implement simple completion detection
- [ ] Test basic functionality

### M3: Testing & Validation (Day 2)
- [ ] Create comparison test
- [ ] Validate equivalent outputs
- [ ] Test error handling paths
- [ ] Performance spot-check

### M4: Documentation & Cleanup (Day 2)
- [ ] Add inline documentation
- [ ] Create complexity comparison table
- [ ] Update any relevant README sections
- [ ] Final code review

## Work Breakdown (Tasks)

### T1.1: Analyze Current Completion Problems (Updated)
**Owner:** context-engineer
**Estimate:** 45m (increased)
**Dependencies:** None
**Milestone:** M1

**Acceptance Tests:**
- Current completion detection mechanisms fully understood
- **Premature completion scenarios documented** (like the "TUNACODE DONE" example)
- "TUNACODE DONE" marker usage patterns identified
- Complex state transition rules that cause false completion mapped
- Minimum viable feature set defined **with focus on natural completion**

**Files/Interfaces Touched:**
- `src/tunacode/core/agents/main.py:416-605` (read-only)
- `src/tunacode/core/agents/agent_components/response_state.py` (read-only)
- `src/tunacode/core/agents/agent_components/task_completion.py` (read-only)

### T1.2: Design Natural Completion Logic (Updated)
**Owner:** context-engineer
**Estimate:** 60m (increased)
**Dependencies:** T1.1
**Milestone:** M1

**Acceptance Tests:**
- **TypeScript-inspired completion logic designed**: `has_tool_calls ? continue : stop`
- **"TUNACODE DONE" markers eliminated** from completion detection
- Simplified function signature matches original
- **Natural completion flow documented**: AI decides when done, not artificial markers
- Tool execution strategy preserves existing interfaces

**Files/Interfaces Touched:**
- Design document with comparison to TypeScript pattern
- Completion logic flowchart showing before/after

### T1.3: Implement Skeleton Function
**Owner:** context-engineer
**Estimate:** 60m
**Dependencies:** T1.2
**Milestone:** M1

**Acceptance Tests:**
- `process_request_simple()` function compiles
- Basic while loop structure in place
- Helper function stubs created
- Type annotations correct

**Files/Interfaces Touched:**
- `src/tunacode/core/agents/main.py` (add new function)

### T2.1: Implement Tool Execution Logic
**Owner:** context-engineer
**Estimate:** 90m
**Dependencies:** T1.3
**Milestone:** M2

**Acceptance Tests:**
- `_execute_node_tools()` function complete
- Tool execution from agent nodes working
- Error handling preserved but simplified
- Boolean return value correct

**Files/Interfaces Touched:**
- `src/tunacode/core/agents/main.py` (implement helper function)

### T2.2: Implement Core Processing Loop (Updated)
**Owner:** context-engineer
**Estimate:** 120m
**Dependencies:** T2.1
**Milestone:** M2

**Acceptance Tests:**
- **TypeScript-inspired while loop implemented**: simple boolean conditions
- Tool execution working without forced completion
- Streaming callbacks functional
- **Natural completion detection working**: stops only when AI makes no tool calls
- **No "TUNACODE DONE" markers** in completion logic
- Agent response generation correct

**Files/Interfaces Touched:**
- `src/tunacode/core/agents/main.py` (implement main loop)

### T3.1: Create Completion Detection Test (Updated)
**Owner:** context-engineer
**Estimate:** 90m
**Dependencies:** T2.2
**Milestone:** M3

**Acceptance Tests:**
- **Test for premature completion scenarios**: verify simplified version doesn't stop early
- Test comparing simple vs complex versions
- **Validate natural completion works**: AI continues until no more tool calls
- Error cases handled appropriately
- **Test prevents "didn't finish, had to ask again" problems**

**Files/Interfaces Touched:**
- `tests/core/agents/test_main.py` (add completion detection test)

### T3.2: Validate Edge Cases
**Owner:** context-engineer
**Estimate:** 60m
**Dependencies:** T3.1
**Milestone:** M3

**Acceptance Tests:**
- Empty responses handled correctly
- Tool execution errors handled
- Streaming interruption tested
- Performance reasonable vs complex version

**Files/Interfaces Touched:**
- `tests/core/agents/test_main.py` (extend test)

### T4.1: Document Implementation
**Owner:** context-engineer
**Estimate:** 45m
**Dependencies:** T3.2
**Milestone:** M4

**Acceptance Tests:**
- Inline comments explaining simplification approach
- Complexity comparison table added
- Usage examples provided
- Documentation builds successfully

**Files/Interfaces Touched:**
- `src/tunacode/core/agents/main.py` (add documentation)

### T4.2: Final Review & Cleanup
**Owner:** context-engineer
**Estimate:** 30m
**Dependencies:** T4.1
**Milestone:** M4

**Acceptance Tests:**
- Code passes `ruff check --fix .`
- All tests passing
- No regressions in existing functionality
- Ready for production use

**Files/Interfaces Touched:**
- `src/tunacode/core/agents/main.py` (final cleanup)
- `tests/core/agents/test_main.py` (ensure no test failures)

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Simplified version loses critical functionality | High | Medium | Keep complex version, add comprehensive tests | Test failures or missing features |
| Type interface mismatches | Medium | Low | Match original function signature exactly | Compilation errors |
| Performance regression | Medium | Medium | Spot-check performance, optimize if needed | Significant slowdown in testing |
| Tool execution compatibility issues | High | Low | Preserve existing tool callback interface | Tool execution failures |

## Test Strategy

**Completion Detection Focused Test Approach:**
- **PRIMARY**: Test that simplified version doesn't stop prematurely like current system
- Create test scenarios where complex version fails with early "TUNACODE DONE"
- Validate simplified version continues until AI naturally stops (no tool calls)
- Test basic scenarios: simple queries, tool execution, streaming
- **Focus on completion behavior** rather than identical implementations
- Use test data fixtures for consistent comparison of completion timing

## References

### Research Document
- `memory-bank/research/2025-09-29_11-08-14_state_and_task_logic.md` - Complete analysis of current complex architecture

### Core Implementation Files
- `src/tunacode/core/agents/main.py:416-605` - Current complex implementation (190+ lines)
- `src/tunacode/core/agents/agent_components/response_state.py:12` - State management patterns
- `src/tunacode/core/agents/agent_components/tool_executor.py:14` - Tool execution patterns

### TypeScript Patterns Found
- `dist/opentui/components/REPL.js` - Simple command execution pattern
- `dist/opentui/protocol/process-client.js` - Process communication pattern
- `src/tunacode/core/agents/agent_components/tool_executor.py` - Parallel execution inspiration

### GitHub Repository
- Repository: https://github.com/alchemiststudiosDOTai/tunacode
- Reference Commit: 6b6e6d5

## Agents

### Context-Synthesis Subagent
Deploy to analyze existing implementation patterns and validate that the simplified version maintains critical functionality.

### Codebase-Analyzer Subagent
Deploy to examine type interfaces, dependencies, and ensure the new implementation integrates properly with existing code.

### Codebase-Locator Subagent
Deploy to find additional TypeScript/JavaScript patterns that might inform the simplification approach.

## Final Gate

**Plan Path:** `memory-bank/plan/2025-09-29_11-15-30_simplified_agent_implementation.md`

**Milestones:** 4 (Architecture, Core Features, Testing, Documentation)

**Gates:** 8 total tasks across 4 milestones, each with specific acceptance criteria

**Next Command:** `/execute "memory-bank/plan/2025-09-29_11-15-30_simplified_agent_implementation.md"`

**Success Criteria:** Working simplified agent implementation with equivalent functionality to complex version, validated by comprehensive comparison test.


You're absolutely right - that's confusing! Let me clarify:

## The Confusion

I showed you **JavaScript/TypeScript code** as an example of a **simpler agent loop pattern**, but our **TunaCode codebase is entirely Python**. 

The JS code was just for **architectural inspiration** - showing how their simple `while(true)` loop works. We're **not** trying to integrate JavaScript into our Python codebase.

## What We're Actually Doing

**Taking the JavaScript PATTERN and implementing it in Python:**

### JavaScript Pattern (inspiration):
```javascript
while (true) {
  // 1. Process AI response
  const result = await processor.process(stream)
  
  // 2. Continue if tool calls were made
  if ((await stream.finishReason) === "tool-calls") {
    continue
  }
  
  // 3. Stop if no tool calls - natural completion
  return result
}
```

### Python Implementation (what we're building):
```python
async def process_request_simple(
    message: str,
    model: ModelName, 
    state_manager: StateManager,
    tool_callback: Optional[ToolCallback] = None,
    streaming_callback: Optional[Callable[[str], Awaitable[None]]] = None,
) -> AgentRun:
    """Python implementation of TypeScript-inspired simple loop."""
    
    agent = ac.get_or_create_agent(model, state_manager)
    message_history = _prepare_message_history(state_manager)
    
    while True:
        # 1. Process AI response (Python style)
        async with agent.iter(message, message_history=message_history) as agent_run:
            async for node in agent_run:
                
                # 2. Execute any tool calls (Python style)  
                has_tool_calls = await _execute_node_tools(
                    node, tool_callback, state_manager
                )
                
                # 3. Continue if tool calls were made (same logic, Python syntax)
                if has_tool_calls:
                    continue
                
                # 4. Stop if no tool calls - natural completion (Python return)
                return ac.AgentRunWrapper(agent_run, node.result or ac.SimpleResult(""))
```

## Key Point

- **JavaScript code**: Just showing the **pattern/architecture**
- **Our implementation**: Pure **Python** using our existing Python libraries and types
- **Same logic**: Simple `while True` loop with tool-call-based completion detection
- **Same benefit**: Natural completion without premature "TUNACODE DONE" stops

