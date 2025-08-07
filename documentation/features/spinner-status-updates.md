# Spinner Status Updates

## Overview

TunaCode now has infrastructure to show dynamic spinner messages during tool execution, replacing the generic "Thinking..." message with specific status updates like "Collecting tools (3 buffered)..." or "Executing 4 tools in parallel...".

## Current Status

**Infrastructure: ✅ Complete**
- Spinner update calls are implemented throughout the tool execution flow
- Messages are generated based on tool operations
- Debug logging confirms updates are being called

**Visual Display: ⚠️ Not Yet Working**
- Rich's Status.update() is called successfully
- Terminal display doesn't reflect the updates
- Likely due to prompt_toolkit/Rich interaction in the REPL environment

## Implementation Details

### Key Components

1. **`update_spinner_message()`** in `src/tunacode/ui/output.py`
   - Updates the spinner text using Rich's Status.update()
   - Uses `run_in_terminal()` for thread safety with prompt_toolkit

2. **Tool Descriptions** in `src/tunacode/ui/tool_descriptions.py`
   - `get_tool_description()` - Returns human-readable tool descriptions
   - `get_batch_description()` - Creates messages for parallel tool batches

3. **Integration Points**
   - Tool buffering in `node_processor.py` - Shows "Collecting tools..."
   - Batch execution in `node_processor.py` and `main.py` - Shows "Executing N tools..."
   - Resets to "Thinking..." after completion

### Message Examples

- `"Collecting tools (3 buffered)..."` - During tool collection
- `"Executing 4 tools in parallel..."` - During batch execution
- `"Reading file: /path/to/file.py..."` - For specific tool operations
- `"Searching 2 patterns in parallel..."` - For grep operations

## Debug Logging

Enable with the current implementation to see spinner update flow:
```
[DEBUG] Found tool call: grep
[DEBUG] Adding grep to buffer
[DEBUG] About to call update_spinner_message
[DEBUG] buffered_count: 3
[DEBUG] update_spinner_message called with: [bold #00d7ff]Collecting tools (3 buffered)...[/bold #00d7ff]
[DEBUG] CALLING SPINNER UPDATE WITH: [bold #00d7ff]Collecting tools (3 buffered)...[/bold #00d7ff]
[DEBUG] SPINNER UPDATED!
```

## Future Work

To make the visual updates work, investigate:
1. Terminal refresh mechanisms in prompt_toolkit
2. Alternative spinner implementations (e.g., using prompt_toolkit's own progress indicators)
3. Force-refresh methods for the Rich console
4. Potential conflicts between Rich and prompt_toolkit event loops

## Benefits (When Visual Updates Work)

- Users see what tools are being executed in real-time
- Clear indication of parallel vs sequential execution
- Better understanding of performance optimizations
- Reduced perception of "stuck" operations