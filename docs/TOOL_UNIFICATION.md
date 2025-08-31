# Tool System Unification Documentation

## Overview

The TunaCode tool system has been unified to eliminate triple maintenance of tool definitions across system prompts, XML schemas, and Python implementations. This document describes the new unified system and migration process.

## Architecture

### Core Components

1. **ToolRegistry** (`src/tunacode/tools/registry.py`)
   - Singleton registry storing all tool definitions
   - Categories tools for parallel execution rules
   - Provides lookup methods by name and category

2. **@tool_definition Decorator** (`src/tunacode/tools/decorator.py`)
   - Annotates tool classes with unified metadata
   - Automatically registers tools in the registry
   - Single source of truth for tool definitions

3. **PromptGenerator** (`src/tunacode/tools/prompt_generator.py`)
   - Generates tool documentation from registry
   - Creates OpenAI function call examples
   - Builds parallel execution rules

4. **SystemPromptBuilder** (`src/tunacode/tools/system_builder.py`)
   - Builds system prompts with dynamic tool documentation
   - Supports template placeholders for tool insertion
   - Model-specific optimizations

5. **OpenAIFormatter** (`src/tunacode/tools/openai_formatter.py`)
   - Formats tool calls in OpenAI function calling format
   - Handles argument stringification as required
   - Validates format compliance

6. **FeatureFlags** (`src/tunacode/tools/feature_flags.py`)
   - Controls rollout of unified system
   - Maintains backward compatibility during migration
   - Environment variable configuration

## Tool Categories

Tools are categorized for execution policy enforcement:

- **READ_ONLY**: Safe for parallel execution (grep, glob, read_file, list_dir)
- **WRITE**: File modification tools, sequential only (write_file, update_file)
- **EXECUTE**: System execution tools, sequential only (bash, run_command)
- **TASK_MGMT**: Task management tools (todo)
- **PLANNING**: Planning and workflow tools (present_plan)

## Migration Status

### Completed Phases

✅ **Phase 1**: Core registry and decorator implementation
✅ **Phase 2**: Prompt generation and system building
✅ **Phase 3**: OpenAI function call formatting
✅ **Phase 4**: Integration with existing schema systems
✅ **Phase 5**: Tool migration with decorators
✅ **Phase 6**: Feature flags for controlled rollout

### Migrated Tools

All core tools have been annotated with `@tool_definition`:

- `grep` (ParallelGrep) - READ_ONLY
- `glob` (GlobTool) - READ_ONLY
- `read_file` (ReadFileTool) - READ_ONLY
- `list_dir` (ListDirTool) - READ_ONLY
- `write_file` (WriteFileTool) - WRITE
- `update_file` (UpdateFileTool) - WRITE
- `bash` (BashTool) - EXECUTE
- `run_command` (RunCommandTool) - EXECUTE
- `todo` (TodoTool) - TASK_MGMT
- `present_plan` (PresentPlanTool) - PLANNING

## Usage

### Defining a New Tool

```python
from tunacode.tools.decorator import tool_definition
from tunacode.tools.registry import ToolCategory
from tunacode.tools.base import BaseTool

@tool_definition(
    name="my_tool",
    category=ToolCategory.READ_ONLY,
    description="Description for prompts and API",
    parameters={
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Parameter description"
            }
        },
        "required": ["param1"]
    },
    example_args={"param1": "example_value"},
    brief="Short description for listings"
)
class MyTool(BaseTool):
    # Implementation...
```

### Feature Flag Configuration

Enable unified system via environment variables:

```bash
# Enable registry-based schema generation
export TUNACODE_USE_UNIFIED_REGISTRY=true

# Enable dynamic prompt generation
export TUNACODE_USE_DYNAMIC_PROMPTS=true

# Disable XML fallback (full migration)
export TUNACODE_DISABLE_XML=true
```

Or programmatically:

```python
from tunacode.tools.feature_flags import ToolFeatureFlags

# Enable full migration
ToolFeatureFlags.enable_full_migration()

# Check status
status = ToolFeatureFlags.get_migration_status()
```

### Generating Documentation

```python
from tunacode.tools.prompt_generator import PromptGenerator

# Generate all tool documentation
docs = PromptGenerator.generate_all_tools()

# Generate parallel execution rules
rules = PromptGenerator.generate_parallel_rules()
```

### Building System Prompts

```python
from tunacode.tools.system_builder import SystemPromptBuilder

# Build complete system prompt with tools
prompt = SystemPromptBuilder.build_system_prompt(include_tools=True)

# Model-specific optimization
prompt = SystemPromptBuilder.build_for_model("claude-3")
```

## Backward Compatibility

The system maintains full backward compatibility:

1. **Fallback Support**: All integration points check feature flags and fall back to XML-based systems when disabled
2. **Gradual Migration**: Tools can be migrated incrementally without breaking existing functionality
3. **XML Preservation**: Original XML files remain untouched during migration
4. **Schema Parity**: Registry-generated schemas match existing XML schemas

## Testing

Comprehensive test coverage includes:

- `tests/unit/tools/test_registry.py` - Registry functionality
- `tests/unit/tools/test_prompt_generator.py` - Prompt generation
- `tests/unit/tools/test_openai_formatter.py` - OpenAI formatting
- `tests/unit/tools/test_feature_flags.py` - Feature flag behavior

Run tests with:

```bash
cd /home/tuna/tunacode
python -m pytest tests/unit/tools/ -v
```

## Benefits

1. **Single Source of Truth**: Tool metadata defined once in decorators
2. **Consistency**: Eliminates drift between prompts, schemas, and implementations
3. **Maintainability**: Changes to tool definitions automatically propagate
4. **Extensibility**: Easy to add new tools and modify existing ones
5. **Dynamic Generation**: Prompts and schemas generated on-demand
6. **Type Safety**: Structured definitions with validation

## Future Enhancements

- Model-specific prompt optimization
- Tool usage analytics and optimization
- Automatic schema validation
- Enhanced parallel execution policies
- Tool dependency management
