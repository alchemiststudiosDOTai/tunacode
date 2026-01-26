---
title: Types Module
path: src/tunacode/types
type: directory
depth: 1
description: Type definitions, protocols, and dataclasses
exports: [UserConfig, MessageHistory, ModelName, ToolCallback]
seams: [M]
---

# Types Module

## Purpose
Centralizes all type aliases, protocols, and dataclass definitions for type safety and consistency across the codebase.

## Key Components

### base.py
Fundamental type aliases:
- **ModelName** - Model identifier string
- **SessionId** - Session UUID
- **ToolName** - Tool identifier
- **ToolCallId** - Tool call UUID

### dataclasses.py
**Pydantic dataclasses for structured data:**
- **UserConfig** - User configuration structure
- **AgentRun** - Agent execution metadata
- **ToolResult** - Tool execution result
- **ToolCall** - Tool invocation details

### state.py
State-related types:
- **MessageHistory** - List of conversation messages
- **ToolArgs** - Tool argument dictionary
- **ToolProgressCallback** - Progress update callback
- **InputSessions** - Session list structure

### state_structures.py
SessionState sub-structures:
- **ConversationState** - Messages, thoughts, token tracking
- **TaskState** - Todos and original query
- **RuntimeState** - Iteration counters, tool registry, request metadata
- **UsageState** - Per-call and cumulative usage metrics

### tool_registry.py
Tool call lifecycle registry:
- **ToolCallRegistry** - Single source of truth for tool call state

### callbacks.py
Callback type definitions:
- **ToolCallback** - Tool execution callback
- **StreamingCallback** - Response streaming callback
- **ConfirmationCallback** - Tool confirmation callback
- **ProgressCallback** - Generic progress callback

### pydantic_ai.py
**Pydantic-AI Integration Types:**
- **AgentRun** - Extended with pydantic-ai specifics
- **ToolResult** - Tool result wrapper
- Custom type adapters

## Type Categories

### Primitive Aliases
- String types (ModelName, ToolName, etc.)
- Integer IDs (SessionId, ToolCallId)
- Path types (FilePath, DirPath)

### Collection Types
- MessageHistory - List[Message]
- ToolArgs - Dict[str, Any]
- InputSessions - List[SessionInfo]

### Callback Types
- Synchronous and async callbacks
- Progress and streaming callbacks
- Confirmation and authorization callbacks

### Protocol Types
- ToolExecutor protocol
- StateManager protocol
- Renderer protocol

## Integration Points

- **All modules** - Import types for consistency
- **core/state.py** - SessionState, UserConfig
- **core/agents/** - AgentRun, ToolCallback
- **tools/** - ToolArgs, ToolResult
- **ui/** - Callback types

## Seams (M)

**Modification Points:**
- Add new type aliases
- Extend dataclass definitions
- Create new protocols
- Add type validation logic

**Best Practices:**
- All types exported from __init__.py
- Use type aliases over string literals
- Prefer dataclasses over dicts for structure
- Add validation to dataclasses
