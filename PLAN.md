# Architecture Refactor Adoption Plan

## summay of granular task
Drive adoption of the canonical message and state model across production paths while eliminating redundant state tracking and enforcing architectural boundaries. The plan focuses on target outcomes, sequencing, risks, and validation gates, leaving implementation decisions to the delivery team.

## key files
- docs/refactoring/architecture-refactor-plan.md
- docs/refactoring/message-flow-map.md
- docs/refactoring/dependency-diagram.md
- src/tunacode/types/canonical.py
- src/tunacode/utils/messaging/adapter.py
- src/tunacode/core/state.py
- src/tunacode/core/agents/resume/sanitize.py
- src/tunacode/core/agents/agent_components/orchestrator/tool_dispatcher.py
- tests/unit/types/test_canonical.py
- tests/unit/types/test_adapter.py

## deliveable
- A chunk-by-chunk adoption roadmap with prerequisites, risks, and acceptance criteria.
- A clarified ownership model for state, message history, and tool call tracking.
- A parity and architecture validation charter tied to real session data.
- A deprecation schedule for legacy message access patterns and polymorphic flows.

## Context Snapshot
- Canonical types and adapter exist but are not adopted in production paths.
- SessionState remains monolithic with mixed concerns and duplicated tracking.
- Sanitization, tool call tracking, and message access are still polymorphic.
- Architecture enforcement tests are missing.

## Task Map

### Task 1: Production Adoption of Canonical Messaging
- Objective: Make canonical messaging the default conceptual model for runtime message access and serialization.
- Scope: Runtime message access patterns, message history representation, and migration safety.
- Dependencies: Adapter stability, parity validation plan, and message flow documentation.
- Acceptance: Production paths use a single canonical access model with legacy fallbacks formally deprecated.
- Risk: Inconsistent handling of legacy formats without parity coverage.

### Task 2: SessionState Decomposition
- Objective: Separate conversation, task, runtime, and usage concerns into distinct ownership boundaries.
- Scope: State ownership, invariants, and API boundaries between sub-states.
- Dependencies: Tool call tracking model and usage metric design alignment.
- Acceptance: Clear sub-state responsibilities with documented invariants and integration points.
- Risk: Hidden coupling that forces multi-module changes for simple updates.

### Task 3: Parity Harness Expansion
- Objective: Prove equivalence between legacy and canonical message interpretations using real session data.
- Scope: Session serialization parity, adapter round-trips, and representative data coverage.
- Dependencies: Access to historical session artifacts and expected behaviors.
- Acceptance: Parity coverage defined, executed, and tied to regression prevention.
- Risk: False confidence from synthetic tests that do not match production data.

### Task 4: Canonical Sanitization Strategy
- Objective: Establish a canonical sanitization flow that operates on unified message structures.
- Scope: Message cleanup rules, dangling tool call handling, and determinism guarantees.
- Dependencies: Tool call registry design and parity tests for sanitized outcomes.
- Acceptance: A single sanitization specification with validated behavior across formats.
- Risk: Divergent cleanup rules leading to state drift or missing tool call linkage.

### Task 5: Tool Call Registry Ownership
- Objective: Converge on a single source of truth for tool call lifecycle and metadata.
- Scope: Lifecycle states, storage ownership, and reconciliation with message history.
- Dependencies: SessionState decomposition and sanitization strategy.
- Acceptance: One authoritative registry with explicit lifecycle semantics and usage constraints.
- Risk: Loss of auditability if metadata becomes fragmented or duplicated.

### Task 6: ReAct State Alignment
- Objective: Standardize ReAct scratchpad representation and lifecycle expectations.
- Scope: Timeline structure, entry typing, and integration with runtime decisions.
- Dependencies: SessionState decomposition and canonical message adoption.
- Acceptance: Typed ReAct state with explicit invariants and compatibility expectations.
- Risk: Incomplete guidance capture if the model is not aligned with runtime usage.

### Task 7: Todo State Alignment
- Objective: Normalize task tracking into typed, auditable todo items.
- Scope: Todo lifecycle, status semantics, and ownership boundaries.
- Dependencies: SessionState decomposition and task orchestration expectations.
- Acceptance: Typed todo structure with consistent status transitions and reporting.
- Risk: Divergent representations causing inconsistent task visibility.

### Task 8: Usage Metrics Consolidation
- Objective: Standardize usage tracking and unify per-call and session totals.
- Scope: Metric definitions, aggregation boundaries, and reporting format.
- Dependencies: SessionState decomposition and runtime usage capture expectations.
- Acceptance: Consistent usage metrics aligned to canonical types and reporting needs.
- Risk: Miscounted usage or incompatible metrics across providers.

### Task 9: Architecture Enforcement Tests
- Objective: Prevent regression on layering rules and state complexity.
- Scope: Dependency direction, state size constraints, and contract adherence.
- Dependencies: Defined architecture rules and boundary decisions from earlier tasks.
- Acceptance: Enforcement checks agreed upon and required for change validation.
- Risk: Untested boundary violations reintroducing coupling.

### Task 10: Legacy Decommission Plan
- Objective: Retire obsolete message access patterns and polymorphic pathways safely.
- Scope: Deprecation policy, removal sequence, and rollback boundaries.
- Dependencies: Successful adoption of canonical messaging and sanitization.
- Acceptance: Legacy paths removed after documented migration completion.
- Risk: Breaking compatibility for historical sessions without parity guarantees.

## Sequencing and Dependencies
- Phase A: Establish parity validation and canonical messaging adoption foundations.
- Phase B: Define ownership boundaries (SessionState, Tool Call Registry, ReAct, Todos, Usage).
- Phase C: Canonical sanitization and enforcement tests.
- Phase D: Legacy decommission and stabilization.

## Validation Charter
- Behavioral parity against historical session artifacts.
- Architectural boundary checks for dependency direction and state size.
- Tool call lifecycle consistency across message history and state ownership.
- Usage metrics consistency across providers and session lifecycles.

## Open Questions to Resolve Before Execution
- Streaming compatibility with immutable canonical structures.
- Availability and representativeness of historical session data.
- Performance impact of canonical conversions under heavy usage.
- Backward compatibility policy for archived sessions.

## Todos
- [ ] Confirm scope owners and success criteria for tasks 1-10.
- [ ] Approve sequencing and dependency assumptions with stakeholders.
- [ ] Define acceptance criteria for parity, sanitization, and registry convergence.
- [ ] Establish deprecation milestones and communication plan for legacy removal.
