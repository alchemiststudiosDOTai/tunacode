---
title: "Multi-Agent Delegation Implementation – Plan"
phase: Plan
date: "2025-11-18 17:09:12"
owner: "Claude (Planning Agent)"
parent_research: "memory-bank/research/2025-11-18_17-01-30_multi-agent-delegation-pydantic-ai.md"
git_commit_at_plan: "df06234"
tags: [plan, multi-agent, delegation, pydantic-ai]
---

## Goal

**PRIMARY OBJECTIVE:** Implement a specialized research agent with read-only tools that can be delegated to from the main agent using pydantic-ai's native delegation pattern, with automatic usage aggregation and limits enforcement.

**Success Criteria:** Main agent can delegate codebase research tasks to a child agent via `research_codebase` tool, with combined usage tracked automatically.

**Non-Goals:**
- Multi-level delegation chains (more than 2 levels deep)
- Manual state management or custom usage tracking
- Message history isolation (accept pydantic-ai defaults)
- MCP server role-based filtering (use defaults for now)

## Scope & Assumptions

### In Scope
1. Create research agent factory with read-only tools (read_file, grep, list_dir, glob)
2. Implement `research_codebase` delegation tool for main agent
3. Create research-specific system prompt in `prompts/research/system.xml`
4. Register delegation tool with main agent's tool list
5. Test basic delegation with usage limit validation
6. ONE integration test to validate delegation works end-to-end

### Out of Scope
- Recursive context stack usage (infrastructure exists but unused)
- Message history isolation between parent/child
- MCP server filtering by role
- Tool strict validation changes
- Multiple specialized agent types (synthesis, planning, etc.)

### Assumptions
- Pydantic-AI's `ctx.usage` automatically aggregates parent + child usage (validated by research)
- `UsageLimits` enforced across entire delegation chain (per pydantic-ai docs)
- Research agent output will be structured JSON dict
- Main agent can decide when to delegate vs. use own tools
- No drift detected in codebase since research commit df06234

### Constraints
- Must use existing tool implementations (no tool modifications)
- Must preserve backward compatibility with existing agent creation
- Must follow tunacode TDD workflow: test-first, minimal implementation
- Must use `ruff check --fix` before committing
- Must update .claude/ KB after implementation

## Deliverables (Definition of Done)

1. **Research Agent Module** (`src/tunacode/core/agents/research_agent.py`)
   - ✅ Factory function `create_research_agent()` exists
   - ✅ Accepts model parameter (same model as main agent, not hardcoded)
   - ✅ Loads research system prompt from `prompts/research/system.xml`
   - ✅ Configured with 4 read-only tools only
   - ✅ Returns structured dict output

2. **Delegation Tool** (`src/tunacode/core/agents/delegation_tools.py`)
   - ✅ `research_codebase()` async function implemented
   - ✅ Accepts `RunContext`, query, directories, max_files params
   - ✅ Gets model from state_manager (same model as main agent)
   - ✅ Delegates to research agent with `ctx.usage` propagation
   - ✅ Returns structured research findings dict

3. **Research System Prompt** (`src/tunacode/prompts/research/system.xml`)
   - ✅ Defines research agent role and constraints
   - ✅ Specifies JSON output schema
   - ✅ Emphasizes read-only operations

4. **Main Agent Integration** (modify `src/tunacode/core/agents/agent_components/agent_config.py`)
   - ✅ Import delegation_tools module
   - ✅ Register `research_codebase` as Tool in main agent's tool list
   - ✅ Preserve existing tool configuration

5. **Integration Test** (`tests/test_research_agent_delegation.py`)
   - ✅ Test validates delegation flow works
   - ✅ Test validates usage aggregation
   - ✅ Test validates UsageLimits enforcement
   - ✅ Test passes with golden baseline established

6. **Knowledge Base Update**
   - ✅ Run `claude-kb add pattern --component agents.delegation`
   - ✅ Document delegation pattern in .claude/patterns/
   - ✅ Run `claude-kb sync --verbose` and `claude-kb validate`

## Readiness (Definition of Ready)

### Prerequisites Met
- ✅ Research document complete and reviewed
- ✅ Read-only tools identified and categorized
- ✅ Pydantic-AI delegation pattern validated
- ✅ No code drift detected since research
- ✅ Prompt directory structure exists (`src/tunacode/prompts/`)
- ✅ Test infrastructure available (`hatch run test`)

### Data/Access Requirements
- ✅ Access to tunacode codebase
- ✅ Write access to create new modules
- ✅ Ability to run tests locally

### Environment Setup
- ✅ `.venv` exists with uv package manager
- ✅ `ruff` available for linting
- ✅ `hatch` configured for test execution

## Milestones

### M1: Research Agent Foundation (Architecture & Skeleton)
**Duration Estimate:** Small
**Dependencies:** None

**Tasks:**
- Create `src/tunacode/core/agents/research_agent.py` with factory stub
- Create `src/tunacode/prompts/research/system.xml` with basic prompt
- Validate imports and module structure

**Acceptance:**
- Module imports without errors
- Factory returns pydantic-ai Agent instance
- Prompt file loads successfully

### M2: Delegation Tool Implementation (Core Feature)
**Duration Estimate:** Medium
**Dependencies:** M1

**Tasks:**
- Implement `src/tunacode/core/agents/delegation_tools.py`
- Implement `research_codebase()` with ctx.usage propagation
- Add proper type hints and docstrings

**Acceptance:**
- Function signature matches spec
- Calls research agent with proper prompt
- Returns structured dict output
- Type checks pass

### M3: Main Agent Integration (Integration & Wiring)
**Duration Estimate:** Small
**Dependencies:** M2

**Tasks:**
- Modify `agent_config.py` to import delegation tool
- Register tool in main agent's tool list
- Validate no regression in existing agent creation

**Acceptance:**
- Main agent creation still works
- New tool appears in agent's tool list
- Existing tests still pass

### M4: Testing & Validation (Quality Assurance)
**Duration Estimate:** Medium
**Dependencies:** M3

**Tasks:**
- Write ONE integration test in `tests/test_research_agent_delegation.py`
- Test delegation flow with simple query
- Validate usage aggregation behavior
- Run full test suite with `hatch run test`

**Acceptance:**
- Integration test passes
- Usage correctly aggregated across parent + child
- No regression in existing tests
- `ruff check` passes

### M5: Documentation & Knowledge Base (Finalization)
**Duration Estimate:** Small
**Dependencies:** M4

**Tasks:**
- Update .claude/patterns/ with delegation pattern
- Run `claude-kb add pattern --component agents.delegation`
- Run `claude-kb sync --verbose && claude-kb validate`
- Create focused git commit

**Acceptance:**
- KB entry created successfully
- Manifest.json updated
- Validation passes
- Changes committed

## Work Breakdown (Detailed Tasks)

### Task 1.1: Create Research Agent Module Skeleton
**Owner:** Executor Agent
**Estimate:** XS
**Dependencies:** None
**Target Milestone:** M1

**Description:** Create `src/tunacode/core/agents/research_agent.py` with factory function stub

**Files Touched:**
- NEW: `src/tunacode/core/agents/research_agent.py`

**Acceptance Tests:**
- [ ] File exists at correct path
- [ ] Imports without errors
- [ ] Factory function signature matches spec

**Implementation Notes:**
```python
# Minimal skeleton
from pydantic_ai import Agent
from tunacode.core.state import StateManager
from tunacode.types import ModelName

def create_research_agent(model: ModelName, state_manager: StateManager) -> Agent:
    """Create research agent with read-only tools.

    IMPORTANT: Uses same model as main agent - do NOT hardcode model selection.
    """
    # TODO: implement
    pass
```

### Task 1.2: Create Research System Prompt
**Owner:** Executor Agent
**Estimate:** S
**Dependencies:** None
**Target Milestone:** M1

**Description:** Create `src/tunacode/prompts/research/system.xml` with research agent instructions

**Files Touched:**
- NEW: `src/tunacode/prompts/research/system.xml`

**Acceptance Tests:**
- [ ] File exists and is valid XML
- [ ] Defines research role clearly
- [ ] Specifies JSON output schema
- [ ] Emphasizes read-only constraint

**Implementation Notes:**
Follow research doc template at lines 691-724

### Task 2.1: Implement Research Agent Factory
**Owner:** Executor Agent
**Estimate:** M
**Dependencies:** Task 1.1, Task 1.2
**Target Milestone:** M2

**Description:** Fully implement `create_research_agent()` with read-only tools

**Files Touched:**
- EDIT: `src/tunacode/core/agents/research_agent.py`

**Acceptance Tests:**
- [ ] Accepts ModelName parameter (same as main agent)
- [ ] Loads system prompt from file
- [ ] Configures exactly 4 read-only tools
- [ ] Sets output_type=dict
- [ ] Returns pydantic-ai Agent instance
- [ ] Tool configuration matches main agent pattern
- [ ] Does NOT hardcode model selection

**Implementation Notes:**
Reference research doc lines 583-614 for complete implementation, but ensure model parameter is passed through instead of hardcoded "gemini-2.5-flash"

### Task 2.2: Implement Delegation Tool
**Owner:** Executor Agent
**Estimate:** M
**Dependencies:** Task 2.1
**Target Milestone:** M2

**Description:** Create `delegation_tools.py` with `research_codebase()` function

**Files Touched:**
- NEW: `src/tunacode/core/agents/delegation_tools.py`

**Acceptance Tests:**
- [ ] Function accepts RunContext, query, directories, max_files
- [ ] Retrieves current model from state_manager or context
- [ ] Constructs research prompt correctly
- [ ] Calls research agent with same model as main agent
- [ ] Calls research agent with ctx.usage propagation
- [ ] Returns dict with expected schema
- [ ] Type hints correct and complete

**Implementation Notes:**
Reference research doc lines 618-670 for complete pattern, but CRITICAL CHANGE: Do NOT hardcode "gemini-2.5-flash". Extract model from state_manager.session or pass through RunContext dependency injection.

### Task 3.1: Register Delegation Tool with Main Agent
**Owner:** Executor Agent
**Estimate:** S
**Dependencies:** Task 2.2
**Target Milestone:** M3

**Description:** Modify `agent_config.py` to include research delegation tool

**Files Touched:**
- EDIT: `src/tunacode/core/agents/agent_components/agent_config.py`

**Acceptance Tests:**
- [ ] Imports delegation_tools module
- [ ] Creates Tool instance for research_codebase
- [ ] Appends to tools_list before agent creation
- [ ] Existing agent creation logic unchanged
- [ ] Cache invalidation still works

**Implementation Notes:**
Add after line 69 where other tools are listed

### Task 4.1: Write Integration Test
**Owner:** Executor Agent
**Estimate:** M
**Dependencies:** Task 3.1
**Target Milestone:** M4

**Description:** Create ONE test validating delegation flow and usage tracking

**Files Touched:**
- NEW: `tests/test_research_agent_delegation.py`

**Acceptance Tests:**
- [ ] Test creates main agent with delegation tool
- [ ] Test invokes delegation with simple query
- [ ] Test validates structured output returned
- [ ] Test verifies usage aggregation (parent + child)
- [ ] Test validates UsageLimits enforcement
- [ ] Test passes on first run

**Implementation Notes:**
Keep test focused - single happy path validation

### Task 5.1: Update Knowledge Base
**Owner:** Executor Agent
**Estimate:** S
**Dependencies:** Task 4.1
**Target Milestone:** M5

**Description:** Document delegation pattern in .claude/

**Files Touched:**
- .claude/patterns/ (via claude-kb add)
- .claude/manifest.json (via claude-kb sync)

**Acceptance Tests:**
- [ ] `claude-kb add pattern --component agents.delegation` succeeds
- [ ] Pattern entry includes delegation implementation details
- [ ] `claude-kb sync --verbose` shows no drift
- [ ] `claude-kb validate` passes

**Implementation Notes:**
```bash
claude-kb add pattern \
  --component agents.delegation \
  --summary "Pydantic-AI multi-agent delegation with usage aggregation" \
  --error "None" \
  --solution "See research_agent.py and delegation_tools.py"
```

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| Pydantic-AI ctx.usage doesn't aggregate as expected | High | Low | Test early in M4; fallback to manual tracking if needed | Integration test fails usage validation |
| Research agent system prompt too restrictive | Medium | Medium | Start with permissive prompt, refine based on behavior | Agent refuses valid research queries |
| Tool import conflicts or circular dependencies | Medium | Low | Use lazy imports and module-level caching | Import errors during agent creation |
| UsageLimits not enforced across delegation | High | Low | Validate in integration test; document limitation if broken | Test shows limits not enforced |
| Main agent doesn't know when to delegate | Low | High | Accept as design trade-off; improve system prompt if needed | Agent never uses research tool |

## Test Strategy

### Test Types
1. **Unit Tests:** NONE (keep scope minimal)
2. **Integration Tests:** ONE test in `tests/test_research_agent_delegation.py`
3. **Manual Tests:** Validate delegation via CLI with sample queries

### Integration Test Coverage
**File:** `tests/test_research_agent_delegation.py`

**Test Case:** `test_research_agent_delegation_with_usage_limits()`
- Given: Main agent with research delegation tool
- When: User query triggers delegation to research agent
- Then:
  - Research agent executes with read-only tools
  - Structured dict returned
  - Usage aggregated (parent + child tokens combined)
  - UsageLimits enforced across both agents

**Validation Points:**
```python
# 1. Delegation succeeds
assert result.output is not None
assert isinstance(result.output, dict)

# 2. Usage aggregated
assert result.usage().requests >= 2  # Parent + child
assert result.usage().input_tokens > 0
assert result.usage().output_tokens > 0

# 3. Limits enforced
assert result.usage().requests <= usage_limits.request_limit
assert result.usage().total_tokens <= usage_limits.total_tokens_limit
```

### Golden Baseline
**Establish baseline:** First successful test run becomes golden baseline
**Validation:** Future changes must maintain delegation behavior

## References

### Research Document
- [memory-bank/research/2025-11-18_17-01-30_multi-agent-delegation-pydantic-ai.md](../research/2025-11-18_17-01-30_multi-agent-delegation-pydantic-ai.md)

### Key Code Locations
**Agent Architecture:**
- [src/tunacode/core/agents/agent_components/agent_config.py:191-304](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234/src/tunacode/core/agents/agent_components/agent_config.py#L191-L304) - Current agent factory
- [src/tunacode/core/agents/main.py:298-492](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234/src/tunacode/core/agents/main.py#L298-L492) - Request orchestration

**Tool Definitions:**
- [src/tunacode/tools/read_file.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234/src/tunacode/tools/read_file.py)
- [src/tunacode/tools/grep.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234/src/tunacode/tools/grep.py)
- [src/tunacode/tools/list_dir.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234/src/tunacode/tools/list_dir.py)
- [src/tunacode/tools/glob.py](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234/src/tunacode/tools/glob.py)
- [src/tunacode/constants.py:61-69](https://github.com/alchemiststudiosDOTai/tunacode/blob/df06234/src/tunacode/constants.py#L61-L69) - Tool categorization

**External Documentation:**
- [Pydantic-AI Multi-Agent Delegation](https://ai.pydantic.dev/multi-agent-applications/#agent-delegation)
- [Pydantic-AI Usage Tracking](https://ai.pydantic.dev/api/usage/)
- [Pydantic-AI RunContext](https://ai.pydantic.dev/api/run/#pydantic_ai.RunContext)

## Agents & Subagents

**Primary Executor:** Context-engineer:execute agent
**Allowed Subagents (Max 3 concurrent):**
1. `codebase-analyzer` - For analyzing existing agent architecture
2. `context-synthesis` - For validating implementation correctness
3. NONE - Keep scope tight

**Subagent Usage Strategy:**
- Use `codebase-analyzer` ONLY if unfamiliar code patterns encountered
- Use `context-synthesis` ONLY for final validation before KB update
- Default to direct implementation without subagent overhead

## Final Gate

**Plan Summary:**
- **Plan Path:** `memory-bank/plan/2025-11-18_17-09-12_multi-agent-delegation-implementation.md`
- **Milestones:** 5 (Architecture, Core Feature, Integration, Testing, Documentation)
- **Tasks:** 6 atomic tasks with clear acceptance criteria
- **Gates:** Each milestone has explicit acceptance criteria
- **Test Count:** ONE integration test (respects "at most ONE" constraint)

**Drift Detection:** ✅ No code changes detected since research commit df06234

**Execution Readiness:** ✅ All prerequisites validated, ready to execute

**Next Command:**
```bash
/context-engineer:execute "memory-bank/plan/2025-11-18_17-09-12_multi-agent-delegation-implementation.md"
```

---

**Plan Validation Checklist:**
- [x] Single focused goal clearly stated
- [x] Scope explicitly defined (in/out)
- [x] Deliverables have measurable DoD
- [x] Prerequisites validated (DoR)
- [x] Milestones ordered logically
- [x] Tasks have acceptance tests
- [x] Risks identified with mitigations
- [x] Test strategy respects "at most ONE" constraint
- [x] No coding performed during planning
- [x] Document saved in correct format
- [x] References complete and accurate
- [x] Plan focuses on EXECUTION not exploration
