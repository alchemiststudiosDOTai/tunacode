# Pydantic Tool Integration for TunaCode

## Executive Summary

This document outlines the integration strategy for properly implementing Pydantic-based tool definitions in TunaCode, ensuring full compatibility with OpenAI's tool calling API while eliminating conflicts between manual system prompt examples and auto-generated schemas.

## Current State Analysis

### What Already Exists

1. **@tool_definition Decorator**
   - Stores JSON schemas in `ToolDefinition.parameters`
   - Captures complete tool metadata (name, description, parameters)
   - Already integrated with ToolRegistry

2. **ToolRegistry System**
   - Provides centralized tool lookup
   - Category-based filtering
   - Dynamic tool discovery

3. **Partial pydantic-ai Integration**
   - `Tool()` wrapper exists in codebase
   - Example template showing `ReadToolInput(BaseModel)` pattern
   - Foundation for Pydantic model usage

### What's Missing

1. **JSON Schema → Pydantic BaseModel Converter**
   - Need automatic conversion from existing schemas
   - Must preserve all parameter definitions

2. **Pydantic Model Generation**
   - System to generate BaseModel classes from @tool_definition schemas
   - Bridge between function signatures and BaseModel pattern

3. **Tool Registration Bridge**
   - Convert from `Tool(function)` to `Tool(BaseModel)` pattern
   - Maintain backward compatibility

## The Problem Being Solved

### Current Issues

```python
# Problem 1: Manual examples in system prompt
"""
<example>

<name>read_file</name>
<parameters>
{"path": "src/main.py"}  # Manual example
</parameters>

</example>
"""

# Problem 2: Function signatures create mismatches
def read_file(file_path: str):  # Parameter name: file_path
    pass

# But pydantic-ai generates:
class ReadFileInput(BaseModel):
    path: str  # Different parameter name!

# Problem 3: No validation of model responses
# Model might send invalid parameters that aren't caught
```

### Root Cause
- **Conflicting Sources of Truth**: Manual system prompt examples vs auto-generated schemas
- **Parameter Name Mismatches**: Function signatures vs BaseModel field names
- **No Validation Layer**: Direct function calls without Pydantic validation

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────┐
│           @tool_definition                  │
│         (Existing Decorator)                │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│      JSON Schema Extraction                 │
│   (From ToolDefinition.parameters)          │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│    Pydantic Model Generator (NEW)           │
│  Converts JSON Schema → BaseModel           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│      Tool Registration with pydantic-ai     │
│         Tool(BaseModel, function)           │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│         OpenAI API Integration              │
│    (Automatic schema generation)            │
└─────────────────────────────────────────────┘
```

### Implementation Steps

#### Step 1: Create Schema to Pydantic Converter

```python
from pydantic import BaseModel, Field, create_model
from typing import Any, Dict, Type

class SchemaConverter:
    """Converts JSON schemas to Pydantic BaseModel classes"""

    @staticmethod
    def json_schema_to_pydantic(
        name: str,
        schema: Dict[str, Any]
    ) -> Type[BaseModel]:
        """
        Convert a JSON schema to a Pydantic BaseModel class

        Args:
            name: Name for the generated model class
            schema: JSON schema dictionary

        Returns:
            Dynamically created Pydantic BaseModel class
        """
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        fields = {}
        for field_name, field_schema in properties.items():
            field_type = _json_type_to_python(field_schema["type"])
            is_required = field_name in required

            if is_required:
                fields[field_name] = (field_type, Field(
                    description=field_schema.get("description", "")
                ))
            else:
                fields[field_name] = (Optional[field_type], Field(
                    default=None,
                    description=field_schema.get("description", "")
                ))

        return create_model(f"{name}Input", **fields)
```

#### Step 2: Modify Tool Registration

```python
from pydantic_ai import Tool

class EnhancedToolRegistry:
    """Extended ToolRegistry with Pydantic support"""

    def register_with_pydantic(self, agent):
        """Register all tools with pydantic-ai agent"""

        for tool_name, tool_def in self.tools.items():
            # Generate Pydantic model from schema
            input_model = SchemaConverter.json_schema_to_pydantic(
                tool_name,
                tool_def.parameters
            )

            # Get the original function
            func = tool_def.function

            # Create wrapper that converts BaseModel to function args
            def create_wrapper(f, model):
                async def wrapper(input_data: model) -> Any:
                    # Convert Pydantic model to dict
                    kwargs = input_data.model_dump()
                    # Call original function
                    return await f(**kwargs)
                return wrapper

            # Register with pydantic-ai
            agent.register_tool(
                Tool(
                    input_model,
                    create_wrapper(func, input_model),
                    name=tool_name,
                    description=tool_def.description
                )
            )
```

#### Step 3: Remove Manual System Prompt Examples

```python
# BEFORE: Manual examples in system prompt
system_prompt = """
You have access to these tools:
<example>

<name>read_file</name>
<parameters>{"path": "src/main.py"}</parameters>

</example>
"""

# AFTER: Let pydantic-ai handle everything
system_prompt = """
You have access to tools for file operations, code analysis, and more.
The available tools and their schemas will be provided automatically.
"""
# pydantic-ai adds tool schemas to the API call automatically
```

## OpenAI Tool Calling Compatibility

### How OpenAI Tool Calling Works

1. **Schema Submission**
   ```json
   {
     "tools": [{
       "type": "function",
       "function": {
         "name": "read_file",
         "description": "Read contents of a file",
         "parameters": {
           "type": "object",
           "properties": {
             "path": {"type": "string", "description": "File path"}
           },
           "required": ["path"]
         }
       }
     }]
   }
   ```

2. **Model Response**
   ```json
   {
     "tool_calls": [{
       "id": "call_123",
       "type": "function",
       "function": {
         "name": "read_file",
         "arguments": "{\"path\": \"src/main.py\"}"
       }
     }]
   }
   ```

3. **Validation & Execution**
   - Pydantic validates the arguments
   - Type checking happens automatically
   - Errors are caught before execution

### Benefits of Pydantic Integration

| Aspect | Without Pydantic | With Pydantic |
|--------|-----------------|---------------|
| **Schema Generation** | Manual JSON schemas | Automatic from BaseModel |
| **Validation** | Manual or none | Automatic with type checking |
| **Documentation** | Separate from code | Integrated in BaseModel |
| **Type Safety** | Runtime errors | Compile-time + runtime checks |
| **Consistency** | Multiple sources of truth | Single source: BaseModel |

## Migration Strategy

### Phase 1: Infrastructure (Week 1)
- [ ] Implement SchemaConverter class
- [ ] Create test suite for converter
- [ ] Validate against existing tools

### Phase 2: Integration (Week 2)
- [ ] Extend ToolRegistry with Pydantic support
- [ ] Create backward compatibility layer
- [ ] Test with pydantic-ai agent

### Phase 3: Migration (Week 3)
- [ ] Convert existing tools one by one
- [ ] Remove manual system prompt examples
- [ ] Update documentation

### Phase 4: Validation (Week 4)
- [ ] End-to-end testing with OpenAI API
- [ ] Performance benchmarking
- [ ] Production rollout with feature flags

## Connection to Simple Agent Example

The Pydantic tool integration can be understood in the context of a simple agent implementation. Here's how the concepts map:

### 1. Tool Definition Comparison

**Pydantic Integration (Recommended)**
```python
@tool_definition(
    name="add_numbers",
    description="Add two numbers together",
    category=ToolCategory.MATH,
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "number", "description": "First number"},
            "b": {"type": "number", "description": "Second number"}
        },
        "required": ["a", "b"]
    }
)
async def add_numbers(a: float, b: float) -> ToolResult:
    try:
        result = a + b
        return ToolResult(success=True, result=result)
    except Exception as e:
        return ToolResult(success=False, message=str(e))
```

**Simple Agent Example**
```python
class CalculatorTool:
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "name": "add_numbers",
            "description": "Add two numbers together",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }

    @classmethod
    async def execute(cls, a: float, b: float) -> Dict[str, Any]:
        return {"result": a + b}
```

### 2. Key Differences

| Feature | Pydantic Integration | Simple Example |
|---------|----------------------|----------------|
| **Definition** | Uses `@tool_definition` decorator | Manual class with methods |
| **Validation** | Built-in Pydantic validation | Manual validation |
| **Integration** | Works with ToolRegistry | Standalone |
| **Error Handling** | Structured ToolResult | Manual dict returns |
| **Type Safety** | Full type hints | Basic type hints |

### 3. Migration Path

To migrate from the simple example to full Pydantic integration:

1. Add `@tool_definition` decorator to your tool functions
2. Replace manual schema definitions with Pydantic models
3. Update tool registration to use the ToolRegistry
4. Modify agent code to use the new tool calling pattern

## Example: Complete Tool Definition

### Before (Current State)

```python
@tool_definition(
    name="read_file",
    description="Read contents of a file",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file"
            }
        },
        "required": ["file_path"]
    }
)
async def read_file(file_path: str) -> str:
    """Read file contents"""
    with open(file_path, 'r') as f:
        return f.read()
```

### After (With Pydantic)

```python
# Auto-generated from @tool_definition
class ReadFileInput(BaseModel):
    """Input for read_file tool"""
    file_path: str = Field(description="Path to the file")

# Original function remains unchanged
@tool_definition(...)
async def read_file(file_path: str) -> str:
    """Read file contents"""
    with open(file_path, 'r') as f:
        return f.read()

# Registration with pydantic-ai
agent.register_tool(
    Tool(
        ReadFileInput,
        lambda input: read_file(input.file_path),
        name="read_file",
        description="Read contents of a file"
    )
)
```

## Key Advantages

### 1. Single Source of Truth
- BaseModel defines everything: schema, validation, documentation
- No conflicting manual examples
- Automatic synchronization

### 2. Type Safety
- Compile-time type checking
- Runtime validation
- Clear error messages

### 3. OpenAI Compatibility
- Proper JSON schema format
- Automatic parameter validation
- Consistent with OpenAI best practices

### 4. Developer Experience
- Auto-completion in IDEs
- Clear documentation
- Easier testing

## Testing Strategy

### Unit Tests
```python
def test_schema_converter():
    """Test JSON schema to Pydantic conversion"""
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"}
        },
        "required": ["path"]
    }

    Model = SchemaConverter.json_schema_to_pydantic("ReadFile", schema)

    # Test valid input
    instance = Model(path="/tmp/test.txt")
    assert instance.path == "/tmp/test.txt"

    # Test validation
    with pytest.raises(ValidationError):
        Model()  # Missing required field
```

### Integration Tests
```python
async def test_openai_tool_calling():
    """Test end-to-end with OpenAI API"""
    agent = create_agent_with_pydantic_tools()

    response = await agent.run("Read the file at /tmp/test.txt")

    # Verify tool was called correctly
    assert_tool_called("read_file", {"file_path": "/tmp/test.txt"})
```

## Key Findings from Implementation Analysis

### 1. System Prompt Conflict
- **Issue**: Manual JSON examples in system.md conflict with pydantic-ai's auto-generation
- **Impact**: Duplicate and potentially conflicting tool documentation
- **Solution**: Remove all manual tool examples from system.md

### 2. Working Approach vs Documentation
- **Current**: Using `Tool(function)` pattern which works perfectly
- **Documentation**: Suggests `Tool(BaseModel)` pattern
- **Reality**: `Tool(function)` is simpler and pydantic-ai introspects function signatures automatically
- **Decision**: Stick with `Tool(function)` - no need for complex BaseModel conversion

### 3. Manual JSON Parsing
- **Found**: `node_processor.py` has manual JSON parsing code
- **Issue**: This may be unnecessary with pydantic-ai handling everything
- **Action**: Clean up redundant manual JSON parsing

### 4. Safety Utilities Bypassed
- **Existing**: JSON safety validation in `json_utils.py`
- **Current**: Not being used in the pydantic-ai flow
- **Consideration**: Evaluate if pydantic-ai's validation is sufficient

### Summary of Findings
**No JSON parser updates needed**, but we should:
1. Remove all manual tool examples from system.md
2. Let pydantic-ai handle all JSON schema generation
3. Clean up redundant manual JSON parsing in node_processor.py
4. Stick with `Tool(function)` pattern since it's working

The current `Tool(function)` approach is simpler and working - pydantic-ai introspects the function signature and generates schemas automatically. No need for the complex BaseModel conversion that was initially planned.

## Important Discovery
The wrapper function at module level (line 197 in read_file.py) with signature `async def read_file(file_path: str)` is what pydantic-ai uses for schema generation. The function parameter names become the tool parameter names automatically.

## OpenRouter Integration Test Results

### Test Script Created
```python
# /home/tuna/tunacode/test_openrouter_tools.py
# Successfully tested OpenRouter with pydantic-ai tool calling
# Key findings:
# 1. OpenRouter works with provider="openrouter" parameter
# 2. Environment variable must be OPENROUTER_API_KEY
# 3. Tool calls are properly executed and return results
# 4. Model: anthropic/claude-3.5-sonnet works correctly
```

### Working Configuration
```python
os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-YOUR-KEY-HERE"
model = OpenAIModel(
    "anthropic/claude-3.5-sonnet",
    provider="openrouter"  # NOT base_url parameter
)
```

### TunaCode Tool Integration Test
```python
# Successfully tested TunaCode's actual read_file tool
from tunacode.tools.read_file import read_file  # Import wrapper function

agent = Agent(
    model=model,
    tools=[read_file]  # Works directly with pydantic-ai
)
```

### Test Results
- Tool discovery works
- Tool execution works
- Multiple tool calls in sequence work
- File reading and listing operations successful
- TunaCode's read_file wrapper function works with OpenRouter
- Parameter name `file_path` is correctly handled
- Deprecation warning: use `result.output` instead of `result.data`

## Conclusion

The Pydantic integration strategy solves the fundamental conflict between manual system prompt examples and auto-generated schemas while ensuring full OpenAI compatibility. By leveraging TunaCode's existing infrastructure (@tool_definition, ToolRegistry), we can implement this with minimal disruption while gaining significant benefits in type safety, validation, and developer experience.

The key insight is that Pydantic BaseModels should be the single source of truth for tool schemas, eliminating the need for manual examples and ensuring consistency across the entire tool calling pipeline.

## References

- [OpenAI Tool Calling Documentation](https://platform.openai.com/docs/guides/function-calling)
- [Pydantic-AI Documentation](https://ai.pydantic.dev/)
- [TunaCode Tool Unification Documentation](./TOOL_UNIFICATION.md)
- [OpenAI Community Discussion on Pydantic](https://community.openai.com/t/pydantic-function-schema-tips/)
