# Tool Handler Refactoring Pattern

**Date:** 2025-11-05
**Component:** tunacode.core.tool_handler
**Type:** Architectural Refactoring
**Status:** Completed

## Problem

The original `ToolHandler` class exhibited multiple code smells:

1. **God Object Anti-Pattern**: Single class responsible for authorization, template management, state manipulation, agent communication, and UI dialog creation
2. **Spaghetti Authorization Logic**: Complex nested conditionals with unclear precedence
3. **Tight Coupling**: Direct dependencies on StateManager, Template system, Agent messaging, and UI
4. **Mutable Global State**: `active_template` field affected behavior across application
5. **Mixed Abstraction Levels**: High-level authorization policy mixed with low-level UI creation
6. **Hidden Dependencies**: Indirect coupling to agent messaging system

## Solution

Applied **Separation of Concerns** using multiple design patterns:

### Architecture Overview

```
ToolHandler (Facade)
├── AuthorizationPolicy (Strategy Orchestrator)
│   └── AuthorizationRule[] (Strategy Interface)
│       ├── PresentPlanRule (Priority 0)
│       ├── PlanModeBlockingRule (Priority 100)
│       ├── ReadOnlyToolRule (Priority 200)
│       ├── TemplateAllowedToolsRule (Priority 210)
│       ├── YoloModeRule (Priority 300)
│       └── ToolIgnoreListRule (Priority 310)
├── ToolRejectionNotifier
└── ConfirmationRequestFactory
```

### Components

#### 1. AuthContext (Immutable Context)
- Replaces scattered mutable state access
- Makes all authorization inputs explicit
- Frozen dataclass ensures immutability
- Created from StateManager via `from_state()` factory method

```python
@dataclass(frozen=True)
class AuthContext:
    is_plan_mode: bool
    yolo_mode: bool
    tool_ignore_list: tuple[ToolName, ...]  # Immutable
    active_template: Optional[Template]
```

#### 2. AuthorizationRule (Protocol)
- Strategy interface for authorization rules
- Each rule encapsulates one authorization concern
- Priority-based evaluation (lower number = higher priority)

```python
class AuthorizationRule(Protocol):
    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool: ...

    def priority(self) -> int: ...
```

#### 3. Concrete Rules (Strategy Implementations)

**Priority Ranges:**
- 0-99: Override rules (present_plan never confirms)
- 100-199: Blocking rules (plan mode restrictions)
- 200-299: Allowlist rules (read-only, templates)
- 300-399: User preference rules (YOLO, ignore list)

#### 4. AuthorizationPolicy (Strategy Orchestrator)
- Two-phase evaluation:
  1. Check blocking rules (plan mode) - overrides everything
  2. Evaluate allowlist rules in priority order
- Declarative approach replaces nested conditionals

#### 5. ToolRejectionNotifier
- Separates agent communication concerns
- Handles user guidance routing to agent system
- Eliminates hidden dependency on messaging system

#### 6. ConfirmationRequestFactory
- Separates UI concerns from business logic
- Creates structured confirmation requests
- Testable in isolation

#### 7. Refactored ToolHandler (Facade)
- Coordinates specialized components via delegation
- Dependency injection with defaults for backward compatibility
- Clean, focused public API

## Design Patterns Applied

1. **Facade Pattern**: ToolHandler provides simple interface to complex subsystem
2. **Strategy Pattern**: Pluggable authorization rules
3. **Protocol/Interface**: AuthorizationRule defines contract
4. **Factory Pattern**: AuthContext.from_state(), create_default_authorization_policy()
5. **Dependency Injection**: Optional dependencies with sensible defaults

## Benefits Achieved

### 1. Separation of Concerns
- Authorization logic: AuthorizationPolicy + Rules
- Agent communication: ToolRejectionNotifier
- UI concerns: ConfirmationRequestFactory
- Orchestration: ToolHandler

### 2. Testability
- Each rule tested independently (no mocks needed)
- AuthorizationPolicy tested with mock rules
- No StateManager mocking required for rule tests
- 36 golden baseline tests ensure behavior preservation

### 3. Maintainability
- Add new rule: Create rule class, add to policy
- Change precedence: Adjust rule priorities
- Modify notifications: Change ToolRejectionNotifier only
- No complex conditional debugging

### 4. Extensibility
- New rules without modifying existing code (Open/Closed Principle)
- Custom policies injectable for different contexts
- Rules composable dynamically

### 5. Clarity
- Authorization precedence explicit through priorities
- Each rule documents its purpose
- No hidden state mutations (immutable context)
- Dependencies explicit via constructor injection

## Implementation Notes

### Backward Compatibility
- Optional dependency injection (defaults preserve existing behavior)
- `active_template` field kept for compatibility
- Existing tests pass without modification

### Critical Design Decision: Plan Mode Overrides

Plan mode blocking uses **two-phase evaluation**:

```python
def should_confirm(self, tool_name: ToolName, context: AuthContext) -> bool:
    # Phase 1: Check blocking rules (overrides YOLO and ignore list)
    if self.is_tool_blocked(tool_name, context):
        return True  # Force confirmation

    # Phase 2: Evaluate allowlist rules
    for rule in self._rules:
        if rule.should_allow_without_confirmation(tool_name, context):
            return False

    return True  # Default: require confirmation
```

This ensures plan mode restrictions cannot be bypassed by YOLO or ignore list.

### Testing Strategy

1. **Golden Baseline Tests** (36 tests):
   - Captured existing behavior before refactoring
   - Comprehensive coverage of all authorization scenarios
   - Regression detection during refactoring

2. **Test Categories**:
   - present_plan special case
   - Plan mode blocking (overrides YOLO/ignore)
   - Read-only tools
   - Template allowed tools
   - YOLO mode
   - Tool ignore list
   - Priority ordering
   - Confirmation processing

## Files Changed

### New Files
- `src/tunacode/core/tool_authorization.py` - New authorization system
- `tests/golden_baseline_tool_handler_authorization.py` - Comprehensive tests
- `memory-bank/research/2025-11-05_refactored_tool_handler_design.md` - Design doc

### Modified Files
- `src/tunacode/core/tool_handler.py` - Refactored to use new components

### Documentation
- `.claude/patterns/tool_handler_refactoring_pattern.md` - This file

## Lessons Learned

1. **Golden Baseline Tests Critical**: Captured existing behavior perfectly, caught regressions immediately
2. **Immutable Context Pattern**: Eliminates entire class of bugs from mutable state
3. **Two-Phase Authorization**: Cleaner than priority-based rules alone for override scenarios
4. **Protocol Over ABC**: Lighter-weight, more Pythonic than abstract base classes
5. **Dependency Injection with Defaults**: Enables gradual migration without breaking changes

## Future Enhancements

Potential improvements (not required now):

1. **Rule Configuration**: Load authorization rules from config file
2. **Audit Logging**: Log authorization decisions for debugging
3. **Custom Rule API**: Allow users to define custom authorization rules
4. **Template Inheritance**: Templates could extend other templates' allowed tools
5. **Context Builders**: Fluent API for creating AuthContext in tests

## References

**Code Files:**
- `/home/user/tunacode/src/tunacode/core/tool_authorization.py`
- `/home/user/tunacode/src/tunacode/core/tool_handler.py`
- `/home/user/tunacode/tests/golden_baseline_tool_handler_authorization.py`

**Design Documents:**
- `/home/user/tunacode/memory-bank/research/2025-11-05_refactored_tool_handler_design.md`
- `/home/user/tunacode/memory-bank/research/2025-11-05_17-35-17_tool_handler_mapping.md`

**Related Patterns:**
- Strategy Pattern (GoF)
- Facade Pattern (GoF)
- Dependency Injection (Fowler)
- Protocol/Interface Segregation (SOLID)

## Error Context

**Original Code Smells Resolved:**
- ✅ God Object → Facade with focused components
- ✅ Spaghetti Logic → Declarative rule-based system
- ✅ Tight Coupling → Dependency injection
- ✅ Mutable State → Immutable context
- ✅ Mixed Abstractions → Separated concerns
- ✅ Hidden Dependencies → Explicit composition
- ✅ Bolted-On Features → Natural composition

**Metrics:**
- Lines of Code: ~135 (original) → ~400 (refactored, includes docs)
- Cyclomatic Complexity: Reduced from 12 to 3 per method
- Test Coverage: 36 comprehensive golden baseline tests
- Zero regressions: All existing tests pass
