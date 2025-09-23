---
title: "Session Save/Load System Research"
date: "2025-09-23"
owner: "context-engineer"
phase: "Research"
tags: ["session-management", "cli", "user-experience", "serialization"]
research_focus: "Session data quality and user-friendly naming"
git_commit: "f8e7035"
---

# Research – Session Save/Load System Improvements

**Date:** 2025-09-23
**Owner:** context-engineer
**Phase:** Research
**Research Focus:** Session data quality and user-friendly naming

## Goal
Identify current issues with session save/load system and determine what needs to be improved for better user experience and data preservation.

## Current Issues Identified

### 1. Session Naming Problems
- **Current**: Sessions use raw UUIDs (e.g., "550e8400-e29b-41d4-a716-446655440000")
- **Problem**: Impossible for users to identify or remember sessions
- **Impact**: Poor user experience when listing/loading sessions

### 2. Data Preservation Issues
- **Current**: `_serialize_message()` function loses critical chat context
- **Lost Data**:
  - `tool_call_id` - breaks tool conversation continuity
  - `timestamp` - removes temporal context
  - `part_kind` - loses message type classification
- **Impact**: Resumed sessions have broken conversations and missing context

### 3. Session Display Issues
- **Current**: Technical UUID format with limited preview
- **Problem**: Users can't quickly identify session content or purpose
- **Impact**: Difficult to find relevant sessions in list

## Findings

### Relevant Files & Why They Matter

#### Core Implementation Files
- `src/tunacode/utils/session_utils.py` → **Primary target** - Contains all serialization, save/load, and listing logic
- `src/tunacode/core/state.py` → Session ID generation (UUID-based) and SessionState structure
- `src/tunacode/cli/commands/implementations/resume.py` → **Primary target** - CLI interface for session management

#### Supporting Files
- `src/tunacode/types.py` → SessionId type definition
- `src/tunacode/constants.py` → Session directory constants
- `src/tunacode/utils/system.py` → Directory management functions
- `src/tunacode/core/agents/agent_components/message_handler.py` → Message structure definitions

#### Test Files (Require Updates)
- `tests/characterization/commands/test_resume_command.py` → Resume command tests
- `tests/characterization/state/test_session_management.py` → Session management tests

### Current Session Data Structure

#### What's Currently Saved (ESSENTIAL_FIELDS)
```python
ESSENTIAL_FIELDS: Tuple[str, ...] = (
    "session_id",           # UUID string
    "current_model",        # Model name
    "user_config",          # User preferences
    "messages",             # Chat messages (simplified)
    "total_cost",           # Cost tracking
    "files_in_context",     # File context
    "session_total_usage",  # Usage statistics
)
```

#### What's Lost During Serialization
- **Tool execution context**: `tool_call_id` linking requests to responses
- **Temporal information**: `timestamp` for conversation flow
- **Message typing**: `part_kind` distinguishing message types
- **Agent reasoning**: Complete thought process and decision context

### Current Session ID Generation
**Location**: `src/tunacode/core/state.py:50`
```python
session_id: SessionId = field(default_factory=lambda: str(uuid.uuid4()))
```
- Uses UUID4 random generation
- No user-friendly naming
- No timestamp integration
- Validation only accepts UUID format

### Current Session Display Format
**Location**: `src/tunacode/cli/commands/implementations/resume.py:104-116`
```
1. 550e8400-e29b-41d4-a716-446655440000  [gpt-4, 12 messages]  @ 2025-09-23 14:30:15 — Last message preview...
```

## Key Patterns / Solutions Found

### 1. Session Storage Pattern
- Sessions stored as JSON in `~/.tunacode/sessions/{session_id}/session_state.json`
- Directory structure already supports different session ID formats
- Existing validation pattern can be updated

### 2. Message Serialization Pattern
- Current `_serialize_message()` function can be extended
- System already filters "useless" technical messages (e.g., training data phrases)
- Pattern exists for handling different message types (dict vs objects)

### 3. Session Listing Pattern
- `list_saved_sessions()` function returns metadata structure
- Current display formatting is centralized in resume command
- Pattern supports adding more metadata (session names, better previews)

## Knowledge Gaps

### 1. User Naming Preferences
- How do users want to name sessions? (manual naming vs auto-generated)
- What information is most important for session identification?

### 2. Message Data Priority
- Which specific message fields are critical vs nice-to-have?
- How to handle complex pydantic-ai message structures?

### 3. Performance Implications
- Impact of preserving more message data on file size and load times
- Balance between data completeness and performance

## Required Changes

### 1. Session Naming System
- Replace UUID generation with timestamp + descriptive name
- Update session validation to accept new naming format
- Improve session display formatting

### 2. Enhanced Message Serialization
- Preserve `tool_call_id`, `timestamp`, `part_kind` fields
- Handle complex pydantic-ai message structures better
- Maintain backward compatibility with existing saved sessions

### 3. User Experience Improvements
- Better session previews and identification
- Clearer session listing format
- Support for session renaming or custom naming

## References

### Implementation Files
- `src/tunacode/utils/session_utils.py` - Core session management
- `src/tunacode/core/state.py` - Session state structure
- `src/tunacode/cli/commands/implementations/resume.py` - CLI interface

### Test Files
- `tests/characterization/commands/test_resume_command.py` - Resume command tests
- `tests/characterization/state/test_session_management.py` - Session management tests

### Documentation
- `memory-bank/plan/2025-09-22_22-30-00_resume_command_implementation.md` - Original implementation plan
- Issue #95 - Resume chat sessions feature request