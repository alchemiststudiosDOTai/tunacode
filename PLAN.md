# Session Save/Load Enhancement Plan

## Overview
Implement user-friendly session naming and improved message serialization for the `/resume` command with minimal code changes and no backward compatibility requirements.

## User Requirements Summary
- **Naming**: Timestamp + auto-description format (`2025-01-23_14-30_python-debugging-session`)
- **Data**: Basic session data, chat messages (user queries + agent responses), tool calls
- **Compatibility**: None required (new feature)
- **Approach**: Incremental, minimal changes, test-driven

---

## Phase 1: Session Naming Enhancement
**Goal**: Replace UUID-based session IDs with user-friendly timestamp + description format

### 1.1 Update Session ID Generation
- **File**: `src/tunacode/core/state.py`
- **Change**: Replace `str(uuid.uuid4())` with timestamp-based naming
- **Format**: `YYYY-MM-DD_HH-MM_description`
- **Fallback**: Generic description if auto-generation fails

### 1.2 Update Session ID Validation
- **File**: `src/tunacode/utils/session_utils.py`
- **Change**: Modify `_is_safe_session_id()` to accept new format
- **Pattern**: Allow alphanumeric, dashes, underscores for new naming scheme

### 1.3 Update Session Display
- **File**: `src/tunacode/cli/commands/implementations/resume.py`
- **Change**: Improve session listing format for new naming scheme
- **Enhancement**: Better readability with timestamp + description parsing

---

## Phase 2: Test Updates
**Goal**: Update the single existing test to work with new session naming

### 2.1 Identify Current Test
- **File**: `tests/characterization/commands/test_resume_command.py`
- **Action**: Review existing test coverage for session save/load

### 2.2 Update Test Expectations
- **Change**: Modify test to expect new session ID format
- **Validation**: Ensure test passes with timestamp-based naming

### 2.3 Add Basic Naming Tests
- **Addition**: Test auto-description generation
- **Coverage**: Test fallback to generic names

---

## Phase 3: Enhanced Message Serialization
**Goal**: Improve message preservation while keeping serialization minimal

### 3.1 Enhance Message Serialization
- **File**: `src/tunacode/utils/session_utils.py`
- **Change**: Update `_serialize_message()` to preserve more context
- **Preserve**: User queries, agent responses, tool calls (basic structure)
- **Exclude**: API keys, sensitive data, complex internal state

### 3.2 Add Description Generation
- **Function**: Create auto-description logic from first few messages
- **Logic**: Extract meaningful keywords from user queries
- **Fallback**: Use generic descriptions for unclear content

### 3.3 Test Enhanced Serialization
- **Addition**: Test message preservation improvements
- **Validation**: Ensure tool calls and basic chat context survive save/load
- **Coverage**: Test description generation from various message types

---

## Implementation Notes

### Minimal Change Strategy
- Reuse existing file structure (`~/.tunacode/sessions/{session_id}/`)
- Keep existing `ESSENTIAL_FIELDS` approach
- No new dependencies required
- Leverage existing JSON persistence patterns

### Auto-Description Logic
- Extract from first 1-3 user messages
- Look for keywords: file names, programming languages, error types
- Max 20 characters for description part
- Sanitize for filesystem safety

### Session ID Format Examples
```
2025-01-23_14-30_python-debugging
2025-01-23_14-31_fix-api-error
2025-01-23_14-32_general-session
```

### Risk Mitigation
- Each phase can be tested independently
- Rollback possible at any phase boundary
- No breaking changes to existing functionality
- Clear validation at each step

---

## Success Criteria

**Phase 1 Complete**: Sessions have readable names, existing functionality preserved
**Phase 2 Complete**: All tests pass with new naming scheme
**Phase 3 Complete**: Enhanced message preservation, auto-description working

**Overall Success**: Users can easily identify and resume sessions with improved context preservation