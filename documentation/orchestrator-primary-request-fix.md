# Orchestrator Primary Request Fix

## Problem

The adaptive orchestrator was incorrectly summarizing results, often showing information from follow-up tasks (like test directory listings) instead of answering the user's original request (like showing a specific file's contents).

## Root Cause

1. **Equal Output Treatment**: All task outputs were aggregated into a single list without tracking which outputs came from primary vs. follow-up tasks
2. **Generic Summarization**: The summarizer used a generic prompt that didn't prioritize answering the original request
3. **Unfocused Follow-ups**: The task generator created follow-up tasks without considering whether the original request was focused on something specific

## Solution

### 1. Primary Task Tracking

Added `primary_request_info` structure to track:
- Original request
- Primary task IDs
- Primary task outputs separately

```python
primary_request_info = {
    "original_request": request,
    "primary_task_ids": [t["id"] for t in initial_tasks],
    "primary_outputs": [],
}
```

### 2. Context-Aware Summarization

Updated the `summarize_results` method in `FeedbackLoop`:
- Accepts `primary_request_info` parameter
- Separates primary outputs from follow-up outputs
- Uses an improved system prompt that explicitly instructs the LLM to prioritize the original request

```python
system_prompt = """You are summarizing the results of task execution.

CRITICAL: Your PRIMARY goal is to answer the original request. Focus on the primary task results that directly address what the user asked for.

Instructions:
1. First and foremost, answer the original request using the primary task results
2. If the user asked to see a specific file, show its contents from the primary output
3. Only mention follow-up/additional findings if they add important context
4. Do NOT let follow-up task outputs overshadow the main answer
5. Be concise but complete in answering the original request"""
```

### 3. Focused Follow-up Generation

Enhanced the `generate_followup_tasks` method in `AdaptiveTaskGenerator`:
- Detects focused requests (file references, "show", "read", etc.)
- Limits follow-up tasks for focused requests
- Passes original request context to the task generator

```python
is_focused_request = any([
    "@" in original_request,  # File reference
    "show" in original_request and ("file" in original_request or ".py" in original_request),
    "read" in original_request,
    "contents of" in original_request,
    any("read" in desc.lower() or "file" in desc.lower() for desc in primary_descriptions)
])
```

### 4. Enhanced File Tracking

- Now tracks read_file operations in addition to write operations
- Ensures all first iteration tasks are considered primary

## Benefits

1. **Accurate Summaries**: The orchestrator now correctly answers the original request first
2. **Better Context**: Follow-up information is presented as additional context, not the main answer
3. **Focused Execution**: For specific file requests, unnecessary exploration is minimized
4. **Improved UX**: Users get direct answers to their questions without wading through unrelated output

## Example

Before fix:
- User: "Show me src/tunacode/cli/main.py"
- Output: Details about test directory structure

After fix:
- User: "Show me src/tunacode/cli/main.py"
- Output: Contents of src/tunacode/cli/main.py (with optional related context)

## Files Modified

1. `src/tunacode/core/agents/adaptive_orchestrator.py`
   - Added primary request tracking
   - Enhanced output collection
   - Improved file tracking

2. `src/tunacode/core/analysis/feedback_loop.py`
   - Updated summarize_results with primary request awareness
   - Improved summarization prompt

3. `src/tunacode/core/analysis/task_generator.py`
   - Added focused request detection
   - Limited follow-ups for specific requests