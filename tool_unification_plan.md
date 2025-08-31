# Tool System Unification Implementation Plan

## 1. Overview
Unify TunaCode's three-layer tool system (system prompt, XML schemas, Python implementation) into a single typed source of truth to eliminate maintenance overhead and improve consistency.

## 2. Current State & Key Discoveries
- **System Prompt:** Hardcoded in `src/tunacode/prompts/system.md` (~360 lines)
- **XML Schemas:** 11 files in `src/tunacode/tools/prompts/` loaded via `xml_helper.py` at runtime
- **Python Implementation:** Tools inherit from `BaseTool` in `src/tunacode/tools/base.py`
- **Registration:** Tools wrapped as `pydantic_ai.Tool` in `src/tunacode/core/agents/agent_components/agent_config.py:244-266`
- **Schema Assembly:** `schema_assembler.py` provides OpenAI-compatible function schemas
- **Key Problem:** Triple maintenance requirement for any tool change

## 3. Desired End State
A single decorator-based tool definition system where each tool's name, description, parameters, examples, and category are defined once and automatically generate system prompts, schemas, and maintain execution logic consistency.

## 4. What We're NOT Doing
- Changing the actual tool execution logic
- Modifying the pydantic-ai integration layer
- Altering the UI logging mechanisms
- Changing the error handling patterns
- Modifying the agent's core architecture

## 5. Implementation Approach
Introduce a `@tool_definition` decorator that captures all tool metadata in a single place, maintaining backward compatibility during migration, then systematically port each tool and remove the XML layer once verified.

---

## Phase 1: Create Tool Registry Infrastructure

### Overview
Build the foundation for unified tool definitions without changing existing behavior.

### Changes Required:
- **File:** `src/tunacode/tools/registry.py` (new)
- **Changes:** Create decorator and registry system
  ```python
  from dataclasses import dataclass
  from typing import List, Dict, Any, Optional, Type
  from enum import Enum

  class ToolCategory(Enum):
      READ_ONLY = "read_only"
      FILE_WRITE = "file_write"
      SYSTEM = "system"
      PLANNING = "planning"

  @dataclass
  class ToolDefinition:
      name: str
      category: ToolCategory
      description: str
      parameters: Dict[str, Any]
      examples: List[tuple[str, str]]
      tool_class: Type['BaseTool']

  class ToolRegistry:
      _instance = None
      _tools: Dict[str, ToolDefinition] = {}

      @classmethod
      def register(cls, definition: ToolDefinition):
          cls._tools[definition.name] = definition
  ```

- **File:** `src/tunacode/tools/decorator.py` (new)
- **Changes:** Create the decorator
  ```python
  def tool_definition(name: str, category: str, description: str, examples: List = None):
      def decorator(cls):
          # Register tool with metadata
          ToolRegistry.register(ToolDefinition(...))
          return cls
      return decorator
  ```

### Success Criteria:
**Automated Verification:**
- [ ] Import test passes: `python -c "from tunacode.tools.registry import ToolRegistry"`
- [ ] Decorator test passes: `python -c "from tunacode.tools.decorator import tool_definition"`
- [ ] Unit tests pass: `hatch run test tests/test_tool_registry.py`

**Manual Verification:**
- [ ] Registry can store and retrieve tool definitions
- [ ] Decorator properly annotates classes without breaking them

---

## Phase 2: Bridge System Prompt Generation

### Overview
Generate tool documentation from registry instead of hardcoded system.md content.

### Changes Required:
- **File:** `src/tunacode/tools/prompt_generator.py` (new)
- **Changes:** Create prompt generation from registry
  ```python
  class PromptGenerator:
      @staticmethod
      def generate_tool_section(tool: ToolDefinition) -> str:
          # Generate markdown documentation for tool
          # Include examples formatted properly

      @staticmethod
      def generate_batching_rules() -> str:
          # Generate batching rules from categories
  ```

- **File:** `src/tunacode/prompts/system_builder.py` (new)
- **Changes:** Build system prompt dynamically
  ```python
  def build_system_prompt(include_tools: bool = True) -> str:
      base_prompt = load_base_prompt()  # Non-tool parts
      if include_tools:
          tool_docs = PromptGenerator.generate_all_tools()
          return base_prompt.replace("{{TOOLS}}", tool_docs)
  ```

### Success Criteria:
**Automated Verification:**
- [ ] Generated prompt contains all tool descriptions: `python scripts/verify_prompt_generation.py`
- [ ] Batching rules match current groupings: `python scripts/verify_batching_rules.py`
- [ ] Tests pass: `hatch run test tests/test_prompt_generator.py`

**Manual Verification:**
- [ ] Generated system prompt visually matches current format
- [ ] Tool examples render correctly in markdown

---

## Phase 3: Schema Assembly Integration

### Overview
Point schema_assembler.py to use registry for consistent parameter definitions.

### Changes Required:
- **File:** `src/tunacode/tools/schema_assembler.py`
- **Changes:** Modify to pull from registry
  ```python
  def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
      definition = ToolRegistry.get(tool_name)
      if not definition:
          return self._legacy_schema(tool_name)  # Fallback

      return {
          "name": definition.name,
          "description": definition.description,
          "parameters": definition.parameters
      }
  ```

- **File:** `src/tunacode/tools/base.py`
- **Changes:** Add registry lookup in get_tool_schema()
  ```python
  def get_tool_schema(self) -> Dict[str, Any]:
      # Try registry first
      if definition := ToolRegistry.get(self.tool_name):
          return {"name": definition.name, ...}
      # Fall back to existing implementation
      return self._legacy_schema()
  ```

### Success Criteria:
**Automated Verification:**
- [ ] Schema tests pass: `hatch run test tests/test_schema_assembler.py`
- [ ] OpenAI format validation: `python scripts/validate_schemas.py`
- [ ] Backward compatibility test: `python scripts/test_legacy_tools.py`

**Manual Verification:**
- [ ] Schemas match expected OpenAI function format
- [ ] All parameters have proper types and descriptions

---

## Phase 4: Pilot Migration - Grep Tool

### Overview
Port grep tool as proof of concept to validate the entire flow.

### Changes Required:
- **File:** `src/tunacode/tools/grep.py`
- **Changes:** Add decorator and consolidate definitions
  ```python
  @tool_definition(
      name="grep",
      category=ToolCategory.READ_ONLY,
      description="Search file contents using regular expressions",
      parameters={
          "type": "object",
          "properties": {
              "pattern": {"type": "string", "description": "Regex pattern"},
              "directory": {"type": "string", "description": "Directory to search", "default": "."}
          },
          "required": ["pattern"]
      },
      examples=[
          ("grep('TODO')", "Find all TODO comments"),
          ("grep('class.*Test')", "Find test classes")
      ]
  )
  class GrepTool(BaseTool):
      # Existing implementation unchanged
  ```

### Success Criteria:
**Automated Verification:**
- [ ] Grep tool works: `python -c "from tunacode.tools.grep import GrepTool"`
- [ ] Schema matches XML version: `python scripts/compare_grep_schemas.py`
- [ ] Integration test: `hatch run test tests/test_grep_migration.py`

**Manual Verification:**
- [ ] Grep tool executes correctly in agent
- [ ] System prompt includes grep documentation
- [ ] No regression in grep functionality

---

## Phase 5: Migrate Remaining Tools

### Overview
Systematically migrate all 11 tools to the new system.

### Changes Required:
- **Files to migrate:**
  - `src/tunacode/tools/bash.py`
  - `src/tunacode/tools/glob.py`
  - `src/tunacode/tools/list_dir.py`
  - `src/tunacode/tools/read_file.py`
  - `src/tunacode/tools/write_file.py`
  - `src/tunacode/tools/update_file.py`
  - `src/tunacode/tools/run_command.py`
  - `src/tunacode/tools/todo.py`
  - `src/tunacode/tools/present_plan.py`
  - `src/tunacode/tools/exit_plan_mode.py`

### Success Criteria:
**Automated Verification:**
- [ ] All tool imports work: `python scripts/test_all_tool_imports.py`
- [ ] Schema comparison passes: `python scripts/compare_all_schemas.py`
- [ ] Full test suite: `hatch run test`

**Manual Verification:**
- [ ] Each tool executes correctly
- [ ] System prompt includes all tools
- [ ] Tool categorization is correct

---

## Phase 6: Remove XML Layer

### Overview
Delete XML files and remove xml_helper.py references once all tools migrated.

### Changes Required:
- **Delete:** `src/tunacode/tools/prompts/` directory (all 11 XML files)
- **File:** `src/tunacode/tools/xml_helper.py`
- **Changes:** Remove or deprecate with warning
- **File:** `src/tunacode/tools/base.py`
- **Changes:** Remove XML fallback logic from prompt() and get_tool_schema()

### Success Criteria:
**Automated Verification:**
- [ ] No XML imports remain: `grep -r "xml_helper" src/`
- [ ] No XML file references: `grep -r "_prompt.xml" src/`
- [ ] Tests still pass: `hatch run test`

**Manual Verification:**
- [ ] Agent starts without XML files present
- [ ] All tools function correctly

---

## Phase 7: Documentation and Testing

### Overview
Update documentation and expand test coverage for the new system.

### Changes Required:
- **File:** `documentation/tools/tool_development.md` (new)
- **Changes:** Guide for adding new tools with decorator
- **File:** `tests/test_tool_consistency.py` (new)
- **Changes:** Verify prompt/schema/implementation alignment
- **File:** `.claude/development/tool_system.md` (new)
- **Changes:** Technical documentation of the unified system

### Success Criteria:
**Automated Verification:**
- [ ] Documentation builds: `python scripts/build_docs.py`
- [ ] Coverage report shows >90%: `hatch run test --cov`
- [ ] Consistency tests pass: `hatch run test tests/test_tool_consistency.py`

**Manual Verification:**
- [ ] Documentation is clear and complete
- [ ] Examples in docs work when copied
- [ ] New tool can be added following the guide

---

## 6. Testing Strategy
- Unit tests for each new component (registry, decorator, generator)
- Integration tests comparing old vs new schemas
- End-to-end tests verifying tool execution unchanged
- Snapshot tests for generated prompts
- Performance tests ensuring no runtime degradation

## 7. Migration & Rollback
- Keep XML parsing as fallback during migration
- Feature flag to toggle between old/new system
- Automated comparison scripts to verify parity
- Git tags at each phase for easy rollback
- Parallel testing in separate branch before merge

## 8. References
- Original Analysis: `/home/tuna/tunacode/prompt-xml.md`
- System Prompt: `src/tunacode/prompts/system.md`
- Tool Registration: `src/tunacode/core/agents/agent_components/agent_config.py:244-266`
- XML Files: `src/tunacode/tools/prompts/` (11 files)
- Base Tool: `src/tunacode/tools/base.py`
