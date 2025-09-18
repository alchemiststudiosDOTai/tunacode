---
title: "Research – Streaming Retry and Buffered Tool Flush Architecture"
date: "2025-09-18T15:21:12+00:00"
owner: "Claude Code"
phase: "Research"
tags: ["streaming", "tool-buffer", "retry-logic", "flush-mechanism", "tool-call-id"]
git_commit: "5cb1ed9545b3eb28be58cae5e5ea77ca5d3ea05f"
last_updated: "2025-09-18T15:21:12+00:00"
last_updated_by: "Claude Code"
---

# Research – Streaming Retry and Buffered Tool Flush Architecture

**Date:** 2025-09-18
**Owner:** Claude Code
**Phase:** Research

## Goal
Summarize all *existing knowledge* about streaming retry logic and buffered tool flush mechanisms before investigating the current tool_call_id persistence issue.

- **Additional Search:**
  - `grep -ri "stream.*retry" .claude/`
  - `grep -ri "tool_call_id" .claude/`
  - `grep -ri "buffer.*flush" .claude/`

## Findings

### Relevant files & why they matter:

#### Core Implementation Files
- **`src/tunacode/core/agents/agent_components/buffer_flush.py`** → Contains `flush_buffered_read_only_tools()` helper function (line 19)
- **`src/tunacode/core/agents/agent_components/streaming.py`** → Contains `stream_model_request_node()` method (line 32) and streaming retry logic (lines 250-288)
- **`src/tunacode/core/agents/main.py`** → Contains `_maybe_stream_node_tokens()` method (line 240) and main retry coordination logic (lines 468-647)
- **`src/tunacode/core/agents/agent_components/node_processor.py`** → Contains tool buffering logic (lines 381-396) and truncation guard (lines 191-214)

#### Test Files
- **`tests/characterization/agent/test_streaming.py`** → Contains test for streaming flush before retry (lines 30-31)
- **`tests/characterization/agent/test_process_request.py`** → Contains main agent process tests

#### Research Documentation
- **`documentation/development/buffered_tool_flush_streaming.md`** → Original research document detailing the streaming retry issue
- **`memory-bank/research/2025-09-18_13-18-41_model_iteration_2_tool_call_buffer_issue.md`** → Historical research on tool_call_id persistence
- **`memory-bank/plan/2025-09-18_13-29-20_tool_call_buffer_race_condition_fix.md`** → Comprehensive fix plan for buffer race conditions

### Key Architecture Components

#### 1. Tool Buffer System
- **`ToolBuffer` class** (`tool_buffer.py:6-25`): Manages buffered read-only tools (grep, read_file, list_dir, glob)
- **Buffering Logic**: Read-only tools are buffered for parallel execution, write tools execute immediately
- **Performance Pattern**: Buffering provides parallel execution benefits while maintaining API compliance

#### 2. Streaming Retry Mechanisms
- **Retry Triggers**: Empty responses, unproductive iterations, iteration caps, truncation guard
- **Critical Pattern**: Buffer flush happens BEFORE any retry logic in all scenarios
- **Error Recovery**: Streaming failures degrade gracefully after 1 retry attempt

#### 3. Tool Call ID Persistence
- **Pydantic-AI Integration**: tool_call_id is part of the tool call structure maintained through the part object lifecycle
- **Session State Tracking**: Tool calls tracked in `state_manager.session.tool_calls` (lines 518-527)
- **API Compliance**: Critical for matching tool-call → tool-return pairs in Pydantic-AI API

## Key Patterns / Solutions Found

#### **Buffer Flush Timing Pattern**
```python
# Critical pattern: flush BEFORE any retry/early exit
if retry_condition:
    await flush_buffered_read_only_tools(...)  # ALWAYS first
    # Then handle retry logic
```

#### **Multiple Retry Paths All Route Through Buffer Flush**
1. **Empty Response** (`main.py:496-508`): Flushes before handling empty responses
2. **Unproductive Iteration** (`main.py:522-540`): Flushes before nudging agent to act
3. **Iteration Cap** (`main.py:578-608`): Flushes before max iteration handling
4. **Truncation Guard** (`node_processor.py:191-214`): Flushes before truncation detection
5. **Streaming Retry** (`streaming.py:252-288`): Flushes before retry attempt

#### **Race Condition Mitigation**
The implementation addresses critical race conditions where tool buffering could cause API rejection during retries. The fix ensures buffer flush happens BEFORE any retry logic.

#### **State Machine Integration**
- **ResponseState**: Tracks agent processing state transitions
- **Buffer Flush Operations**: Respect state machine rules
- **Invalid State Prevention**: Prevents invalid transitions during retry operations

## Current Issue Analysis

Based on the research, the current failure pattern is:

1. **Root Cause**: Provider rejects second streaming attempt with missing `tool` response for outstanding `tool_call_id`
2. **Flush Helper Invoked**: Log shows `origin="stream-retry"` flush occurs
3. **Persistence Issue**: Same `tool_call_id` persists in provider transcript despite flush
4. **Suspected Causes**:
   - Provider request already queued before flush completes
   - Missing synthetic tool-return message generation
   - Buffer repopulation after flush during retry

## Knowledge Gaps

### Missing Implementation Details
- **Exact mechanism** of how synthetic tool-return messages should be generated during streaming retries
- **Provider request timing** - whether the retry request is built before or after flush completion
- **Session state mutation** patterns needed for proper tool call cleanup

### Testing Gaps
- **Integration testing** between streaming retries and tool call persistence
- **End-to-end testing** of the complete streaming failure recovery flow
- **Performance testing** of buffer flush timing during streaming failures
- **Error scenario testing** for various tool_call_id persistence edge cases

### Configuration and Environment
- **Provider-specific behavior** around tool call persistence during streaming
- **Network timing** effects on flush completion vs request building
- **Concurrency patterns** that might affect buffer state during streaming

## References

### Core Implementation Files
- `src/tunacode/core/agents/agent_components/buffer_flush.py:19` - flush_buffered_read_only_tools()
- `src/tunacode/core/agents/agent_components/streaming.py:32` - stream_model_request_node()
- `src/tunacode/core/agents/main.py:240` - _maybe_stream_node_tokens()
- `src/tunacode/core/agents/main.py:468-647` - process_request() retry coordination
- `src/tunacode/core/agents/agent_components/node_processor.py:381-396` - tool buffering logic

### Research Documentation
- `documentation/development/buffered_tool_flush_streaming.md` - Current issue analysis
- `memory-bank/research/2025-09-18_13-18-41_model_iteration_2_tool_call_buffer_issue.md` - Historical tool_call_id research
- `memory-bank/plan/2025-09-18_13-29-20_tool_call_buffer_race_condition_fix.md` - Race condition fix plan

### Test Coverage
- `tests/characterization/agent/test_streaming.py` - Streaming buffer flush tests
- `tests/characterization/agent/test_process_request.py` - Main agent process tests

### Key Integration Points
- Buffer flush called from: main.py (lines 348, 498, 526, 579), streaming.py (line 257), node_processor.py (line 200)
- All retry paths route through flush_buffered_read_only_tools() with specific origin tracking
- Tool call persistence maintained through session state and Pydantic-AI part object lifecycle
