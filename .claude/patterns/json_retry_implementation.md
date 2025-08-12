# JSON Concatenation Recovery System

## Overview
Comprehensive JSON parsing system with retry logic, concatenated object splitting, and enhanced error recovery for CLI tool arguments.

## Problem
The LLM sometimes emits concatenated JSON objects like `{"filepath": "main.py"}{"filepath": "__init__.py"}` for tool arguments, causing "Invalid JSON: Extra data" errors. Standard JSON parsing fails, and recovery mechanisms didn't handle these cases.

## Solution
Multi-layered recovery system with:
1. Enhanced parse_args() with retry logic and concatenated JSON handling
2. New json_utils.py module for safe JSON splitting and validation
3. Improved error recovery with JSON-specific keywords and recovery paths
4. Updated system prompt with explicit JSON formatting rules
5. Comprehensive test coverage for all scenarios

## Implementation Details

### 1. Enhanced Command Parser (`src/tunacode/cli/repl_components/command_parser.py`)
```python
def parse_args(args) -> ToolArgs:
    if isinstance(args, str):
        try:
            # First: Retry logic for transient failures
            return retry_json_parse(args, max_retries=10, base_delay=0.1, max_delay=5.0)
        except json.JSONDecodeError as e:
            if "Extra data" in str(e):
                # Second: Handle concatenated JSON objects
                result = safe_json_parse(args, allow_concatenated=True)
                return result[0] if isinstance(result, list) else result
```

### 2. JSON Utilities Module (`src/tunacode/utils/json_utils.py`)
```python
def safe_json_parse(json_string: str, tool_name: Optional[str] = None,
                   allow_concatenated: bool = False) -> Union[Dict, List[Dict]]

def split_concatenated_json(json_string: str, strict_mode: bool = True) -> List[Dict]

def validate_tool_args_safety(objects: List[Dict], tool_name: Optional[str] = None) -> bool
```
- Robust concatenated JSON object splitting using brace counting
- Safety validation for read-only vs write tools
- Custom ConcatenatedJSONError for unsafe operations

### 3. Enhanced Error Recovery (`src/tunacode/cli/repl_components/error_recovery.py`)
```python
# Extended keyword filtering
tool_keywords = ["tool", "function", "call", "schema", "json", "extra data", "validation"]

# JSON-specific recovery paths
if "extra data" in error_str or "concatenated" in error_str:
    # Handle malformed args in structured tool calls
```

### 4. System Prompt Updates (`src/tunacode/prompts/system.md`)
- Explicit JSON formatting rules: "Output exactly one JSON object per tool call"
- Examples of correct vs incorrect tool argument formats
- Guidance on using arrays for multiple items

## Usage Examples

### Basic Tool Argument Parsing
```python
# Standard case - single JSON object
args = parse_args('{"filepath": "main.py"}')  # Works

# Concatenated case - automatically recovered
args = parse_args('{"filepath": "main.py"}{"filepath": "init.py"}')  # Returns first object
```

### Safe JSON Parsing with Concatenation Support
```python
# Parse with concatenation handling
result = safe_json_parse(
    '{"file": "a.py"}{"file": "b.py"}',
    tool_name="Read",  # Read-only tool
    allow_concatenated=True
)
# Returns: [{"file": "a.py"}, {"file": "b.py"}] for read-only tools
# Returns: {"file": "a.py"} for write tools (safety)
```

## Testing Coverage
- **Retry Logic:** 15 tests covering exponential backoff, max retries, error handling
- **Concatenated JSON:** 10 tests for splitting, merging, safety validation
- **Error Recovery:** 8 tests for keyword matching, recovery paths, edge cases
- **Integration:** End-to-end tests with actual tool execution scenarios

## Benefits
1. **Robust Error Recovery:** Handles both transient failures and concatenated JSON
2. **Safety-First Approach:** Validates tool safety before executing multiple objects
3. **Transparent Operation:** Logs recovery attempts without user interruption
4. **Backward Compatibility:** Existing single JSON objects continue to work
5. **Comprehensive Testing:** High confidence in edge case handling

## Key Files Modified
- `src/tunacode/cli/repl_components/command_parser.py` - Enhanced parse_args()
- `src/tunacode/utils/json_utils.py` - New JSON utilities module
- `src/tunacode/cli/repl_components/error_recovery.py` - JSON error keywords
- `src/tunacode/prompts/system.md` - JSON formatting guidelines
- `tests/test_command_parser_retry.py` - Retry logic tests
- `tests/test_json_concatenation_recovery.py` - Concatenation tests

## Recovery Flow
1. **First Attempt:** Standard json.loads()
2. **Retry Phase:** Exponential backoff for transient failures
3. **Concatenation Detection:** Check for "Extra data" error
4. **Safe Splitting:** Parse concatenated objects with validation
5. **Safety Check:** Validate against READ_ONLY_TOOLS list
6. **Fallback:** Return first object if multiple detected for write tools
