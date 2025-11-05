# Refactored ToolHandler Architecture Design

**Date:** 2025-11-05
**Owner:** claude
**Phase:** Design

## Problem Statement

The current ToolHandler class exhibits multiple code smells:
1. **God Object**: Handles authorization, template management, state manipulation, agent communication, and UI dialog creation
2. **Spaghetti Authorization Logic**: Complex nested conditionals with unclear precedence
3. **Tight Coupling**: Direct dependencies on StateManager, Template, Agent system, and UI
4. **Mutable Global State**: active_template field affects behavior across application
5. **Mixed Abstraction Levels**: High-level policy mixed with low-level UI creation
6. **Hidden Dependencies**: Indirect coupling to agent messaging system
7. **Bolted-On Features**: Template logic doesn't naturally integrate

## Design Goals

1. **Single Responsibility Principle**: Each class has one clear, focused purpose
2. **Declarative Authorization**: Replace imperative checks with composable, declarative rules
3. **Strategy Pattern**: Authorization strategies can be composed and tested independently
4. **Dependency Injection**: Clear dependencies through constructor injection
5. **Testability**: Each component can be unit tested in isolation
6. **Maintainability**: Adding new authorization rules doesn't require modifying existing code

## New Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         ToolHandler                              │
│  (Orchestrator - Facade pattern)                                │
│  - Coordinates authorization, confirmation, and notification     │
└─────────────────┬───────────────────────────────┬────────────────┘
                  │                               │
                  ▼                               ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│   AuthorizationPolicy        │  │  ToolRejectionNotifier       │
│  (Strategy Orchestrator)     │  │  (Agent Communication)       │
│  - Evaluates authorization   │  │  - Notifies agents of        │
│    rules in priority order   │  │    rejections with guidance  │
└────────────┬─────────────────┘  └──────────────────────────────┘
             │
             │ uses multiple
             ▼
┌──────────────────────────────┐
│   AuthorizationRule          │
│  (Strategy Interface)        │
│  - Protocol for rules        │
└────────────┬─────────────────┘
             │
             │ implemented by
             ▼
┌─────────────────────────────────────────────────────┐
│  Concrete Authorization Rules:                      │
│  • ReadOnlyToolRule                                 │
│  • PresentPlanRule                                  │
│  • PlanModeBlockingRule                            │
│  • YoloModeRule                                     │
│  • ToolIgnoreListRule                              │
│  • TemplateAllowedToolsRule                        │
└─────────────────────────────────────────────────────┘
```

### Core Components

#### 1. AuthorizationRule (Protocol)

```python
from typing import Protocol

class AuthorizationRule(Protocol):
    """Protocol for authorization rules that determine if a tool requires confirmation.

    Each rule encapsulates a single authorization concern, making the system
    composable and testable. Rules are evaluated in priority order by
    AuthorizationPolicy.
    """

    def should_allow_without_confirmation(
        self,
        tool_name: ToolName,
        context: AuthContext
    ) -> bool:
        """Check if this rule allows the tool without confirmation.

        Args:
            tool_name: The tool being authorized
            context: Current authorization context with state information

        Returns:
            True if this rule permits the tool without confirmation
        """
        ...

    def priority(self) -> int:
        """Return priority for rule evaluation (lower number = higher priority).

        Priority ensures correct evaluation order:
        - 0-99: Override rules (present_plan)
        - 100-199: Blocking rules (plan mode)
        - 200-299: Allowlist rules (read-only, templates)
        - 300-399: User preference rules (YOLO, ignore list)
        """
        ...
```

#### 2. AuthContext (Data Class)

```python
@dataclass(frozen=True)
class AuthContext:
    """Immutable context for authorization decisions.

    Replaces the mutable active_template field and scattered state reads.
    Makes all authorization inputs explicit and testable.
    """
    is_plan_mode: bool
    yolo_mode: bool
    tool_ignore_list: tuple[ToolName, ...]  # Immutable
    active_template: Optional[Template]

    @classmethod
    def from_state(cls, state: StateManager) -> 'AuthContext':
        """Create context from current state."""
        return cls(
            is_plan_mode=state.is_plan_mode(),
            yolo_mode=state.session.yolo,
            tool_ignore_list=tuple(state.session.tool_ignore),
            active_template=getattr(state.tool_handler, 'active_template', None)
        )
```

#### 3. Concrete Authorization Rules

**Priority 0-99: Override Rules**

```python
class PresentPlanRule:
    """present_plan tool never requires confirmation (has own approval flow)."""

    def priority(self) -> int:
        return 0

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool:
        return tool_name == "present_plan"
```

**Priority 100-199: Blocking Rules**

```python
class PlanModeBlockingRule:
    """Block write tools in plan mode by forcing confirmation."""

    def priority(self) -> int:
        return 100

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool:
        if not context.is_plan_mode:
            return False  # Not applicable in normal mode

        # In plan mode, deny write tools (will require confirmation which shows error)
        return is_read_only_tool(tool_name)
```

**Priority 200-299: Allowlist Rules**

```python
class ReadOnlyToolRule:
    """Read-only tools are always safe."""

    def priority(self) -> int:
        return 200

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool:
        return is_read_only_tool(tool_name)


class TemplateAllowedToolsRule:
    """Tools allowed by active template don't require confirmation."""

    def priority(self) -> int:
        return 210

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool:
        if context.active_template is None:
            return False

        if context.active_template.allowed_tools is None:
            return False

        return tool_name in context.active_template.allowed_tools
```

**Priority 300-399: User Preference Rules**

```python
class YoloModeRule:
    """YOLO mode bypasses all confirmations."""

    def priority(self) -> int:
        return 300

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool:
        return context.yolo_mode


class ToolIgnoreListRule:
    """User-configured ignore list bypasses confirmations."""

    def priority(self) -> int:
        return 310

    def should_allow_without_confirmation(
        self, tool_name: ToolName, context: AuthContext
    ) -> bool:
        return tool_name in context.tool_ignore_list
```

#### 4. AuthorizationPolicy

```python
class AuthorizationPolicy:
    """Orchestrates authorization rules to determine if tools require confirmation.

    Uses Strategy pattern to compose multiple authorization rules. Rules are
    evaluated in priority order, and the first rule that applies determines
    the outcome.

    This replaces the complex nested conditionals in should_confirm() with
    a declarative, testable approach.
    """

    def __init__(self, rules: list[AuthorizationRule]):
        """Initialize with authorization rules.

        Args:
            rules: List of authorization rules to evaluate
        """
        # Sort rules by priority (lower number = higher priority)
        self._rules = sorted(rules, key=lambda r: r.priority())

    def should_confirm(self, tool_name: ToolName, context: AuthContext) -> bool:
        """Determine if tool requires user confirmation.

        Evaluates rules in priority order. First rule that allows the tool
        without confirmation determines the outcome.

        Args:
            tool_name: Tool to authorize
            context: Current authorization context

        Returns:
            True if confirmation required, False otherwise
        """
        for rule in self._rules:
            if rule.should_allow_without_confirmation(tool_name, context):
                return False  # Rule allows tool without confirmation

        # No rule allowed it, require confirmation
        return True

    def is_tool_blocked(self, tool_name: ToolName, context: AuthContext) -> bool:
        """Check if tool is blocked (different from requiring confirmation).

        Used for plan mode blocking where we need to show an error rather than
        just prompting for confirmation.

        Args:
            tool_name: Tool to check
            context: Current authorization context

        Returns:
            True if tool is blocked and should show error
        """
        if not context.is_plan_mode:
            return False

        if tool_name == "present_plan":
            return False

        return not is_read_only_tool(tool_name)
```

#### 5. ToolRejectionNotifier

```python
class ToolRejectionNotifier:
    """Handles communication with agents when tools are rejected.

    Separates agent communication concerns from authorization logic.
    Eliminates hidden dependency on agent messaging system.
    """

    def notify_rejection(
        self,
        tool_name: ToolName,
        response: ToolConfirmationResponse,
        state: StateManager,
    ) -> None:
        """Notify agent that tool execution was rejected.

        Routes user guidance back to agent system to maintain conversation
        context and enable the agent to respond appropriately.

        Args:
            tool_name: Tool that was rejected
            response: User's confirmation response with optional guidance
            state: State manager for routing message to agent
        """
        guidance = getattr(response, "instructions", "").strip()

        if guidance:
            guidance_section = f"User guidance:\n{guidance}"
        else:
            guidance_section = "User cancelled without additional instructions."

        message = (
            f"Tool '{tool_name}' execution cancelled before running.\n"
            f"{guidance_section}\n"
            "Do not assume the operation succeeded; "
            "request updated guidance or offer alternatives."
        )

        create_user_message(message, state)
```

#### 6. ConfirmationRequestFactory

```python
class ConfirmationRequestFactory:
    """Creates confirmation requests from tool information.

    Separates UI concern (confirmation dialog creation) from business logic.
    Makes confirmation request creation testable in isolation.
    """

    def create(
        self, tool_name: ToolName, args: ToolArgs
    ) -> ToolConfirmationRequest:
        """Create a confirmation request from tool information.

        Extracts relevant context (like filepath) for display in confirmation
        dialog.

        Args:
            tool_name: Name of tool requiring confirmation
            args: Tool arguments (may contain filepath, command, etc.)

        Returns:
            Structured confirmation request for UI
        """
        filepath = args.get("filepath")
        return ToolConfirmationRequest(
            tool_name=tool_name,
            args=args,
            filepath=filepath
        )
```

#### 7. Refactored ToolHandler

```python
class ToolHandler:
    """Coordinates tool authorization, confirmation, and rejection handling.

    Refactored to use Facade pattern, delegating to specialized components:
    - AuthorizationPolicy: Determines if confirmation is needed
    - ToolRejectionNotifier: Handles agent communication
    - ConfirmationRequestFactory: Creates confirmation requests

    This eliminates the "God Object" anti-pattern by separating concerns.
    """

    def __init__(
        self,
        state: StateManager,
        policy: Optional[AuthorizationPolicy] = None,
        notifier: Optional[ToolRejectionNotifier] = None,
        factory: Optional[ConfirmationRequestFactory] = None,
    ):
        """Initialize tool handler with injected dependencies.

        Dependencies are optional to maintain backward compatibility during
        refactoring. Defaults are provided for gradual migration.

        Args:
            state: State manager for session state access
            policy: Authorization policy (default: create standard policy)
            notifier: Rejection notifier (default: create standard notifier)
            factory: Confirmation factory (default: create standard factory)
        """
        self.state = state
        self.active_template: Optional[Template] = None  # Kept for compatibility

        # Inject dependencies with defaults
        self._policy = policy or self._create_default_policy()
        self._notifier = notifier or ToolRejectionNotifier()
        self._factory = factory or ConfirmationRequestFactory()

    def _create_default_policy(self) -> AuthorizationPolicy:
        """Create default authorization policy with all standard rules."""
        rules = [
            PresentPlanRule(),
            PlanModeBlockingRule(),
            ReadOnlyToolRule(),
            TemplateAllowedToolsRule(),
            YoloModeRule(),
            ToolIgnoreListRule(),
        ]
        return AuthorizationPolicy(rules)

    def set_active_template(self, template: Optional[Template]) -> None:
        """Set active template for authorization (kept for compatibility)."""
        self.active_template = template

    def should_confirm(self, tool_name: ToolName) -> bool:
        """Determine if tool requires confirmation."""
        context = AuthContext.from_state(self.state)
        return self._policy.should_confirm(tool_name, context)

    def is_tool_blocked_in_plan_mode(self, tool_name: ToolName) -> bool:
        """Check if tool is blocked in plan mode."""
        context = AuthContext.from_state(self.state)
        return self._policy.is_tool_blocked(tool_name, context)

    def process_confirmation(
        self, response: ToolConfirmationResponse, tool_name: ToolName
    ) -> bool:
        """Process confirmation response.

        Handles skip_future preference and rejection notification.

        Args:
            response: User's confirmation response
            tool_name: Tool being confirmed

        Returns:
            True if tool should proceed, False if aborted
        """
        if response.skip_future:
            self.state.session.tool_ignore.append(tool_name)

        if not response.approved or response.abort:
            self._notifier.notify_rejection(tool_name, response, self.state)

        return response.approved and not response.abort

    def create_confirmation_request(
        self, tool_name: ToolName, args: ToolArgs
    ) -> ToolConfirmationRequest:
        """Create confirmation request for UI."""
        return self._factory.create(tool_name, args)
```

## Benefits of Refactored Design

### 1. Separation of Concerns
- **Authorization**: Handled by AuthorizationPolicy and rules
- **Agent Communication**: Isolated in ToolRejectionNotifier
- **UI Concern**: Isolated in ConfirmationRequestFactory
- **Orchestration**: ToolHandler coordinates but doesn't implement details

### 2. Testability
- Each rule can be unit tested independently
- AuthorizationPolicy can be tested with mock rules
- No need to mock StateManager for rule tests
- Clear interfaces make testing straightforward

### 3. Maintainability
- Adding new authorization rule: Create new rule class, add to policy
- Changing authorization precedence: Adjust rule priorities
- Modifying agent notification: Change ToolRejectionNotifier only
- No complex conditional logic to debug

### 4. Extensibility
- New rule types can be added without modifying existing code (Open/Closed Principle)
- Custom authorization policies can be injected for different contexts
- Rules can be composed dynamically based on configuration

### 5. Clarity
- Authorization decision tree is explicit through rule priorities
- Each rule documents its purpose and precedence
- No hidden state mutations (AuthContext is immutable)
- Dependencies are explicit through constructor injection

## Migration Strategy

### Phase 1: Create New Components (Non-Breaking)
1. Implement AuthContext, AuthorizationRule protocol
2. Implement all concrete authorization rules
3. Implement AuthorizationPolicy
4. Implement ToolRejectionNotifier
5. Implement ConfirmationRequestFactory
6. Add comprehensive unit tests for each component

### Phase 2: Refactor ToolHandler (Backward Compatible)
1. Add dependency injection to ToolHandler constructor with defaults
2. Update internal implementation to use new components
3. Keep active_template field for compatibility
4. Ensure all existing tests pass

### Phase 3: Update Integration Points
1. Update tool_executor.py to use new pattern (optional)
2. Update main.py initialization (optional)
3. Remove compatibility shims if desired

### Phase 4: Cleanup
1. Remove old implementation code
2. Update documentation
3. Add new tests for integration scenarios

## Testing Strategy

### Unit Tests
- Test each authorization rule independently
- Test AuthorizationPolicy with mock rules
- Test ToolRejectionNotifier with mock state
- Test ConfirmationRequestFactory with various args

### Integration Tests
- Test complete authorization flow with real rules
- Test rule priority ordering
- Test state transitions (plan mode, YOLO toggle, etc.)

### Golden Baseline Tests
- Capture current behavior before refactoring
- Ensure refactored version produces identical behavior
- Use for regression detection

## Implementation Checklist

- [ ] Create AuthContext dataclass
- [ ] Create AuthorizationRule protocol
- [ ] Implement PresentPlanRule
- [ ] Implement PlanModeBlockingRule
- [ ] Implement ReadOnlyToolRule
- [ ] Implement TemplateAllowedToolsRule
- [ ] Implement YoloModeRule
- [ ] Implement ToolIgnoreListRule
- [ ] Implement AuthorizationPolicy
- [ ] Implement ToolRejectionNotifier
- [ ] Implement ConfirmationRequestFactory
- [ ] Refactor ToolHandler to use new components
- [ ] Write unit tests for all components
- [ ] Write integration tests
- [ ] Ensure all existing tests pass
- [ ] Update documentation
- [ ] Commit and push changes

## References

**Patterns Used:**
- Strategy Pattern: Authorization rules
- Facade Pattern: ToolHandler
- Factory Pattern: ConfirmationRequestFactory
- Protocol/Interface: AuthorizationRule

**Design Principles:**
- Single Responsibility Principle
- Open/Closed Principle
- Dependency Injection
- Composition over Inheritance
- Fail Fast, Fail Loud

**Original Files:**
- `/home/user/tunacode/src/tunacode/core/tool_handler.py` - Current implementation
- `/home/user/tunacode/memory-bank/research/2025-11-05_17-35-17_tool_handler_mapping.md` - Architecture analysis
