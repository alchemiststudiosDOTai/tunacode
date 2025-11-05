# Research – tool_handler.py Mapping

**Date:** 2025-11-05
**Owner:** claude
**Phase:** Research

## Goal
Map out the architecture, patterns, and connections of the tool_handler.py file within the TunaCode codebase.

## Additional Search:
- `grep -ri "tool_handler\|ToolHandler" .claude/`

## Findings

### Core Architecture

**tool_handler.py** (`/root/tunacode/src/tunacode/core/tool_handler.py`) serves as the central authorization layer for tool execution in the TunaCode CLI system. The file implements a **ToolHandler** class that manages tool confirmation logic separate from UI concerns, following the principle of separating business logic from presentation.

### Key Components & Structure

#### 1. **ToolHandler Class** (`lines 19-136`)
```python
class ToolHandler:
    """Handles tool confirmation logic separate from UI."""
```

**Core Fields:**
- `state: StateManager` - Application state management
- `active_template: Optional[Template]` - Current template for tool permissions

**Core Methods:**
- `should_confirm(tool_name)` - Determines if tool requires confirmation
- `is_tool_blocked_in_plan_mode(tool_name)` - Plan mode restrictions
- `process_confirmation(response, tool_name)` - Handles user responses
- `create_confirmation_request(tool_name, args)` - Creates confirmation dialogs

#### 2. **Tool Categorization System**
The file integrates with a sophisticated tool categorization system:

**READ_ONLY_TOOLS** (from `tunacode.constants`):
- `READ_FILE`, `GREP`, `LIST_DIR`, `GLOB`
- `REACT`, `EXIT_PLAN_MODE`
- Automatically skip confirmation

**WRITE_TOOLS**:
- `WRITE_FILE`, `UPDATE_FILE`
- Require confirmation unless pre-approved

**EXECUTE_TOOLS**:
- `BASH`, `RUN_COMMAND`
- Highest security category

#### 3. **Confirmation Decision Tree** (`should_confirm` method, lines 35-62)

The authorization follows this priority:
1. **present_plan** → Never confirm (has own approval flow)
2. **Plan mode** → Block write tools (force confirmation)
3. **Read-only tools** → Skip confirmation
4. **Template allowed tools** → Skip confirmation if in active template
5. **YOLO mode/ignore list** → Skip confirmation
6. **Default** → Require confirmation

### Integration Points & Dependencies

#### 1. **State Management Integration** (`tunacode.core.state`)
- **YOLO Mode**: `state.session.yolo` bypasses all confirmations
- **Tool Ignore List**: `state.session.tool_ignore` stores user preferences
- **Plan Mode**: `state.is_plan_mode()` restricts to read-only operations
- **Session Messages**: Routes user feedback back to agent system

#### 2. **Agent Communication Integration** (`tunacode.core.agents.agent_components.agent_helpers`)
- Uses `create_user_message()` to route tool rejection feedback to agents
- Maintains conversation context through structured messages
- Enables bidirectional tool-agent communication

#### 3. **Template System Integration** (`tunacode.templates.loader`)
- **Template Class**: Defines allowed_tools list for pre-approval
- **TemplateLoader**: Manages template lifecycle from JSON files
- **Permission Override**: Active template can bypass confirmations for specific tools

#### 4. **Type System Integration** (`tunacode.types`)
- **ToolConfirmationRequest**: Structured confirmation dialog data
- **ToolConfirmationResponse**: User response with skip/abort options
- **ToolArgs**: Generic tool argument dictionary

### Key Patterns & Solutions Found

#### 1. **Layered Authorization Pattern**
Multiple independent authorization layers that can each bypass confirmations:
- Template-based pre-approval
- User preference (YOLO mode)
- Session preferences (tool_ignore list)
- Context-based restrictions (plan mode)

#### 2. **Observer Pattern Integration**
ToolHandler observes state changes that affect permissions:
- Template changes immediately affect tool confirmations
- Plan mode transitions block write operations
- YOLO mode toggles bypass all confirmations

#### 3. **Factory Pattern for Confirmations**
`create_confirmation_request()` creates structured confirmation data:
- Extracts filepath from tool args for context
- Standardizes confirmation dialog format
- Enables consistent UI presentation

#### 4. **Error Recovery Pattern**
`process_confirmation()` handles rejection gracefully:
- Routes user guidance back to agent system
- Prevents assumptions about operation success
- Maintains conversation flow with structured feedback

### File Connection Map

**Primary File:** `/root/tunacode/src/tunacode/core/tool_handler.py`

**Direct Dependencies:**
- `/root/tunacode/src/tunacode/constants.py` - Tool categorization constants
- `/root/tunacode/src/tunacode/core/state.py` - State management
- `/root/tunacode/src/tunacode/core/agents/agent_components/agent_helpers.py` - Agent communication
- `/root/tunacode/src/tunacode/templates/loader.py` - Template system
- `/root/tunacode/src/tunacode/types.py` - Type definitions

**Integration Points:**
- `/root/tunacode/src/tunacode/cli/main.py:78-79` - ToolHandler initialization
- `/root/tunacode/src/tunacode/cli/repl_components/tool_executor.py:28` - Tool execution routing
- `/root/tunacode/src/tunacode/cli/commands/template_shortcut.py:57` - Template activation
- `/root/tunacode/src/tunacode/cli/commands/implementations/debug.py:22` - YOLO mode toggle

### State Management Architecture

The ToolHandler integrates with StateManager's session state:
```python
SessionState:
    yolo: bool                    # Bypass all confirmations
    tool_ignore: list[ToolName]   # Per-tool preference bypass
    plan_mode: bool               # Block write operations
    plan_phase: PlanPhase         # Current planning phase
    plan_approved: bool           # Plan execution approval
    messages: MessageHistory      # Conversation context
```

### Template System Architecture

Templates provide workflow-specific tool permissions:
```python
Template:
    name: str                    # Template identifier
    description: str             # Human-readable description
    prompt: str                  # Default prompt with placeholders
    allowed_tools: List[str]     # Pre-approved tool list
    parameters: Dict[str, str]   # Prompt substitution values
    shortcut: Optional[str]      # Command shortcut
```

### Security & Safety Patterns

#### 1. **Fail-Safe Defaults**
- Tools require confirmation by default
- Plan mode blocks potentially dangerous operations
- Read-only tools automatically safe

#### 2. **Explicit Permission Model**
- Templates must explicitly list allowed tools
- Users must consciously bypass confirmations
- Plan mode requires explicit exit

#### 3. **Context-Aware Confirmations**
- Filepath included in confirmation requests
- User guidance routed back to agents
- Clear cancellation messaging

## Knowledge Gaps

- Template system user interface and workflow details
- Plan phase transitions and planning workflow integration
- Agent cache clearing behavior during state changes
- Template distribution and sharing mechanisms

## References

**Core Files:**
- `/root/tunacode/src/tunacode/core/tool_handler.py` - Main implementation
- `/root/tunacode/src/tunacode/constants.py` - Tool categorization
- `/root/tunacode/src/tunacode/core/state.py` - State management
- `/root/tunacode/src/tunacode/types.py` - Type definitions

**Integration Files:**
- `/root/tunacode/src/tunacode/core/agents/agent_components/agent_helpers.py` - Agent communication
- `/root/tunacode/src/tunacode/templates/loader.py` - Template system
- `/root/tunacode/src/tunacode/cli/main.py` - Application initialization
- `/root/tunacode/src/tunacode/cli/repl_components/tool_executor.py` - Tool execution

**Configuration Files:**
- `/root/tunacode/src/tunacode/configuration/defaults.py` - Default settings
- `/root/tunacode/src/tunacode/configuration/settings.py` - Internal tools config

**Command Files:**
- `/root/tunacode/src/tunacode/cli/commands/template_shortcut.py` - Template commands
- `/root/tunacode/src/tunacode/cli/commands/implementations/debug.py` - Debug commands