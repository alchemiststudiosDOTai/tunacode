# JSON Retry Implementation Pattern

## Overview
Implementation of automatic retry logic with exponential backoff for JSON parsing failures in tool batching.

## Problem
The LLM sometimes returns malformed JSON when batching multiple tool calls, causing "Invalid JSON in batched tools" errors. These errors were not being retried, causing unnecessary failures.

## Solution
Created a comprehensive retry mechanism with:
1. Decorator-based retry logic
2. Exponential backoff with configurable delays
3. Custom exception for better error reporting
4. Integration with existing JSON parsing functions

## Implementation Details

### 1. Retry Decorator (`/root/tunacode/src/tunacode/utils/retry.py`)
```python
@retry_on_json_error(
    max_retries=10,
    base_delay=0.1,
    max_delay=5.0
)
```
- Handles both sync and async functions
- Implements exponential backoff: delay = base_delay * (2 ** attempt)
- Caps delay at max_delay to prevent excessive waiting
- Logs each retry attempt with context

### 2. Configuration Constants (`/root/tunacode/src/tunacode/constants.py`)
```python
JSON_PARSE_MAX_RETRIES = 10
JSON_PARSE_BASE_DELAY = 0.1  # Initial delay in seconds
JSON_PARSE_MAX_DELAY = 5.0   # Maximum delay in seconds
```

### 3. Custom Exception (`/root/tunacode/src/tunacode/exceptions.py`)
```python
class ToolBatchingJSONError(TunaCodeError):
    """Raised when JSON parsing fails during tool batching after all retries are exhausted."""
```
- Provides user-friendly error message: "The model is having issues with tool batching"
- Includes retry count and truncated JSON content for debugging
- Preserves original exception for troubleshooting

### 4. Integration Points
- `parse_json_tool_calls()` - Updated to use retry logic
- `extract_and_execute_tool_calls()` - Updated to use retry logic
- Error handling in main.py catches `ToolBatchingJSONError` and continues processing

## Usage Example
```python
# Automatic retry on JSON parsing
parsed = await retry_json_parse_async(
    json_string,
    max_retries=JSON_PARSE_MAX_RETRIES,
    base_delay=JSON_PARSE_BASE_DELAY,
    max_delay=JSON_PARSE_MAX_DELAY,
)
```

## Testing
- Unit tests for retry decorator behavior
- Integration tests for tool batching scenarios
- Tests verify exponential backoff timing
- Tests confirm error messages after max retries

## Benefits
1. Graceful handling of transient JSON parsing failures
2. Improved reliability when LLM returns malformed JSON
3. Better error messages for users
4. Detailed logging for debugging
5. Configurable retry behavior

## Future Enhancements
- Consider adding metrics/telemetry for retry frequency
- Could implement different retry strategies for different error types
- Possibility of adding circuit breaker pattern for persistent failures