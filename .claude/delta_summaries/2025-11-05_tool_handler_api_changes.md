# Delta Summary: Tool Handler API Changes

**Date:** 2025-11-05
**Component:** tunacode.core.tool_handler
**Change Type:** Architectural Refactoring (Non-Breaking)
**Version:** 0.0.77.3

## Summary

Refactored ToolHandler from God Object to Facade pattern with separated concerns. All existing behavior preserved via backward-compatible dependency injection.

## API Changes

### New Module: `tunacode.core.tool_authorization`

**New Public Classes:**

```python
# Immutable context for authorization
class AuthContext:
    is_plan_mode: bool
    yolo_mode: bool
    tool_ignore_list: tuple[ToolName, ...]
    active_template: Optional[Template]

    @classmethod
    def from_state(cls, state: StateManager) -> AuthContext: ...

# Protocol for authorization rules
class AuthorizationRule(Protocol):
    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool: ...

    def priority(self) -> int: ...

# Concrete rule implementations
class PresentPlanRule: ...
class PlanModeBlockingRule: ...
class ReadOnlyToolRule: ...
class TemplateAllowedToolsRule: ...
class YoloModeRule: ...
class ToolIgnoreListRule: ...

# Strategy orchestrator
class AuthorizationPolicy:
    def __init__(self, rules: list[AuthorizationRule]): ...
    def should_confirm(self, tool_name: ToolName, context: AuthContext) -> bool: ...
    def is_tool_blocked(self, tool_name: ToolName, context: AuthContext) -> bool: ...

# Agent communication
class ToolRejectionNotifier:
    def notify_rejection(
        self,
        tool_name: ToolName,
        response: ToolConfirmationResponse,
        state: StateManager,
    ) -> None: ...

# Confirmation request creation
class ConfirmationRequestFactory:
    def create(
        self, tool_name: ToolName, args: ToolArgs
    ) -> ToolConfirmationRequest: ...

# Factory function
def create_default_authorization_policy() -> AuthorizationPolicy: ...

# Helper function
def is_read_only_tool(tool_name: str) -> bool: ...
```

### Modified Module: `tunacode.core.tool_handler`

**ToolHandler Constructor Changes:**

**Before:**
```python
class ToolHandler:
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.active_template: Optional[Template] = None
```

**After:**
```python
class ToolHandler:
    def __init__(
        self,
        state_manager: StateManager,
        policy: Optional[AuthorizationPolicy] = None,
        notifier: Optional[ToolRejectionNotifier] = None,
        factory: Optional[ConfirmationRequestFactory] = None,
    ):
        self.state = state_manager
        self.active_template: Optional[Template] = None  # Kept for compatibility
        self._policy = policy or create_default_authorization_policy()
        self._notifier = notifier or ToolRejectionNotifier()
        self._factory = factory or ConfirmationRequestFactory()
```

**Backward Compatibility:**
- All new parameters are optional with sensible defaults
- Existing code calling `ToolHandler(state_manager)` continues to work
- `active_template` field preserved

**Implementation Changes:**

**Methods with identical signatures (behavior preserved):**
- `set_active_template(template: Optional[Template]) -> None`
- `should_confirm(tool_name: ToolName) -> bool`
- `is_tool_blocked_in_plan_mode(tool_name: ToolName) -> bool`
- `process_confirmation(response: ToolConfirmationResponse, tool_name: ToolName) -> bool`
- `create_confirmation_request(tool_name: ToolName, args: ToolArgs) -> ToolConfirmationRequest`

**Internal implementation changes:**
- `should_confirm()`: Delegates to `_policy.should_confirm()`
- `is_tool_blocked_in_plan_mode()`: Delegates to `_policy.is_tool_blocked()`
- `process_confirmation()`: Uses `_notifier.notify_rejection()`
- `create_confirmation_request()`: Uses `_factory.create()`

**Removed from module:**
- `is_read_only_tool()` function → Moved to `tool_authorization` module

## Behavior Changes

### No Behavioral Changes

All behavior is preserved exactly. This is verified by 36 golden baseline tests covering:

- present_plan special case handling
- Plan mode blocking (overrides YOLO and ignore list)
- Read-only tool allowlisting
- Template allowed tools
- YOLO mode bypass
- Tool ignore list
- Default confirmation requirements
- Priority ordering of rules
- Confirmation request creation
- Confirmation response processing

### Authorization Decision Logic

**Before (imperative):**
```python
def should_confirm(self, tool_name: ToolName) -> bool:
    if tool_name == "present_plan":
        return False
    if self.is_tool_blocked_in_plan_mode(tool_name):
        return True
    if is_read_only_tool(tool_name):
        return False
    if self.active_template and self.active_template.allowed_tools:
        if tool_name in self.active_template.allowed_tools:
            return False
    return not (self.state.session.yolo or tool_name in self.state.session.tool_ignore)
```

**After (declarative):**
```python
def should_confirm(self, tool_name: ToolName) -> bool:
    context = AuthContext.from_state(self.state)
    return self._policy.should_confirm(tool_name, context)
```

**Two-Phase Evaluation:**
1. Check blocking rules (plan mode) - overrides all other rules
2. Evaluate allowlist rules in priority order

**Priority Order:**
0. present_plan (always allowed)
100. Plan mode blocking (forces confirmation for write tools)
200. Read-only tools (always allowed)
210. Template allowed tools
300. YOLO mode
310. Tool ignore list

## Migration Guide

### For Existing Code

**No changes required.** All existing code continues to work:

```python
# This still works exactly as before
handler = ToolHandler(state_manager)
handler.set_active_template(template)
if handler.should_confirm("write_file"):
    # ... show confirmation
```

### For Advanced Use Cases

**Inject custom authorization policy:**

```python
# Create custom rules
custom_rules = [
    PresentPlanRule(),
    ReadOnlyToolRule(),
    CustomAuditRule(),  # Your custom rule
    YoloModeRule(),
]

policy = AuthorizationPolicy(custom_rules)
handler = ToolHandler(state_manager, policy=policy)
```

**Inject custom notifier:**

```python
class AuditingNotifier(ToolRejectionNotifier):
    def notify_rejection(self, tool_name, response, state):
        log_audit_event(tool_name, response)
        super().notify_rejection(tool_name, response, state)

handler = ToolHandler(state_manager, notifier=AuditingNotifier())
```

## Testing Impact

### New Tests

- `tests/golden_baseline_tool_handler_authorization.py` (36 comprehensive tests)

### Existing Tests

All existing tests continue to pass without modification:
- `tests/test_plan_mode.py::TestToolHandler` (all tests pass)
- `tests/characterization/repl_components/test_tool_handler.py` (all tests pass)

## Performance Impact

**Negligible performance change:**
- Authorization now involves 1-6 rule evaluations (typically 2-3)
- Each rule is simple boolean check
- Context creation is lightweight (immutable dataclass)
- No additional I/O or expensive operations

**Estimated overhead:** < 1 microsecond per authorization check

## Import Changes

### Old Import
```python
from tunacode.core.tool_handler import ToolHandler
```

### New Imports (if using advanced features)
```python
from tunacode.core.tool_handler import ToolHandler  # Same as before

# New imports for advanced usage
from tunacode.core.tool_authorization import (
    AuthContext,
    AuthorizationPolicy,
    AuthorizationRule,
    ToolRejectionNotifier,
    ConfirmationRequestFactory,
    create_default_authorization_policy,
)
```

## Deprecations

**None.** No existing APIs are deprecated.

## Breaking Changes

**None.** This is a fully backward-compatible refactoring.

## Rollback Plan

If issues arise:

1. **Immediate rollback:**
   ```bash
   git revert <commit-hash>
   ```

2. **Files to restore:**
   - `src/tunacode/core/tool_handler.py` (original version)

3. **Files to remove:**
   - `src/tunacode/core/tool_authorization.py`
   - `tests/golden_baseline_tool_handler_authorization.py`

4. **No data migration needed** (no persistent state changes)

## Future Compatibility

### Extending Authorization

**To add a new authorization rule:**

1. Create rule class implementing AuthorizationRule protocol
2. Add to default policy or inject custom policy
3. No changes to ToolHandler required

```python
class CustomRule:
    def priority(self) -> int:
        return 250  # Between read-only and template rules

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool:
        # Your logic here
        return False
```

### Configuration-Based Rules

Future enhancement (not implemented):

```yaml
# authorization.yaml
rules:
  - type: present_plan
    priority: 0
  - type: custom
    priority: 150
    config:
      allowed_in_ci: true
```

## Documentation Updates

### Updated Documentation
- `memory-bank/research/2025-11-05_refactored_tool_handler_design.md`
- `.claude/patterns/tool_handler_refactoring_pattern.md`
- `.claude/debug_history/2025-11-05_tool_handler_refactoring.md`
- `.claude/delta_summaries/2025-11-05_tool_handler_api_changes.md` (this file)

### Documentation To Update
- None required (backward compatible)

## Reasoning

### Why This Refactoring?

**Problems solved:**
1. **God Object** → Facade with focused components
2. **Complex Logic** → Declarative rule-based system
3. **Tight Coupling** → Dependency injection
4. **Mutable State** → Immutable context
5. **Hard to Test** → Isolated, testable components
6. **Hard to Extend** → Open/Closed Principle via rules

**Design Principles Applied:**
- Single Responsibility Principle
- Open/Closed Principle
- Dependency Inversion Principle
- Strategy Pattern
- Facade Pattern
- Immutable Data

### Why Backward Compatible?

- Zero disruption to existing code
- Gradual migration possible
- New features available when needed
- Safe to deploy incrementally

## Version History

**0.0.77.3 (2025-11-05)**
- Refactored ToolHandler to use composition
- Added tool_authorization module
- Added 36 golden baseline tests
- Zero breaking changes
- All existing tests pass
