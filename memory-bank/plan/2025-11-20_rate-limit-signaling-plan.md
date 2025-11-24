---
title: "Rate Limit Error Signaling Plan"
phase: Plan
date: "2025-11-20T11:45:00Z"
owner: "Context Engineer Agent"
parent_research: "memory-bank/research/2025-11-20_error_signaling_gaps_analysis.md"
git_commit_at_plan: "36f9c6f"
tags: [plan, rate-limits, error-signaling, rich-ui]
---

## Goal
Implement rich user notifications for rate limit errors to show wait times, token quota information, and retry guidance when OpenAI API rate limits are exceeded.

## Scope & Assumptions
- **In Scope**: OpenAI RateLimitError handling with rich formatting
- **In Scope**: Wait time extraction and countdown display
- **In Scope**: Token quota guidance and retry instructions
- **Out of Scope**: General error handling architecture changes
- **Out of Scope**: Recovery system notifications (handled in separate plan)
- **Assumptions**: OpenAI RateLimitError contains retry-after headers
- **Constraints**: Must maintain existing silent-fail behavior as option

## Deliverables (DoD)
- **Rate Limit Detection**: Specific OpenAI RateLimitError catching
- **Rich Error Display**: Formatted panels with wait times and guidance
- **Countdown Integration**: Real-time countdown showing when requests can resume
- **User Guidance**: Clear instructions for token quota management
- **One Integration Test**: Validates complete rate limit signaling flow

## Readiness (DoR)
- ✅ Research confirms RateLimitError falls through to generic handler
- ✅ UI analysis shows Rich library and countdown system available
- ✅ Codebase has request_delay prevention but no error handling
- ✅ Color theming and panel system ready for rich formatting
- ✅ All dependencies (Rich, OpenAI) already installed

## Milestones

### M1: Rate Limit Detection Framework
- Add OpenAI RateLimitError import and specific catching
- Create rate limit error parsing utilities
- Design error message templates for rate limits

### M2: Rich Notification System
- Implement rich error panels for rate limits
- Add wait time extraction from error headers
- Integrate with existing countdown display system

### M3: User Guidance & Testing
- Add token quota information and retry instructions
- Create integration test for rate limit scenarios
- Add configuration for rate limit notification verbosity

## Work Breakdown (Tasks)

### T001: Add Rate Limit Error Detection
**Owner**: Context Engineer
**Estimate**: 1 hour
**Dependencies**: None
**Target Milestone**: M1

**Acceptance Tests**:
- OpenAI RateLimitError imported and caught specifically
- Error parsing extracts retry-after header
- Token quota information extracted from error details
- Falls back to generic handling if RateLimitError parsing fails

**Files/Interfaces**:
- `src/tunacode/core/agents/main.py:476-490` (modify exception handling)

### T002: Create Rate Limit Message Templates
**Owner**: Context Engineer
**Estimate**: 1 hour
**Dependencies**: T001
**Target Milestone**: M1

**Acceptance Tests**:
- Rate limit exceeded template with wait time placeholder
- Token quota guidance template with usage suggestions
- Retry instructions template with step-by-step guidance
- All templates use existing UI_COLORS error theme

**Files/Interfaces**:
- `src/tunacode/ui/rate_limit_templates.py` (new)

### T003: Implement Rich Rate Limit Display
**Owner**: Context Engineer
**Estimate**: 2 hours
**Dependencies**: T001, T002
**Target Milestone**: M2

**Acceptance Tests**:
- Rich error panel displayed for rate limit errors
- Wait time prominently shown with countdown integration
- Color scheme uses error colors (#dc2626) appropriately
- Panel includes icon and clear "Rate Limit Exceeded" title

**Files/Interfaces**:
- `src/tunacode/ui/rate_limit_display.py` (new)

### T004: Add Countdown Integration
**Owner**: Context Engineer
**Estimate**: 1 hour
**Dependencies**: T003
**Target Milestone**: M2

**Acceptance Tests**:
- Wait time extracted from RateLimitError retry-after header
- Countdown display starts immediately with rich formatting
- Countdown updates every second with live status
- Resume notification sent when countdown completes

**Files/Interfaces**:
- Leverage existing `_sleep_with_countdown()` pattern
- `src/tunacode/core/error_handling/rate_limits.py` (new)

### T005: Create Integration Test
**Owner**: Context Engineer
**Estimate**: 2 hours
**Dependencies**: T003, T004
**Target Milestone**: M3

**Acceptance Tests**:
- Mock OpenAI RateLimitError with retry-after header
- Validate rich panel displays correct wait time
- Test countdown integration and completion notification
- Verify error message content and formatting accuracy

**Files/Interfaces**:
- `tests/test_rate_limit_signaling.py` (new)

### T006: Add Configuration Options
**Owner**: Context Engineer
**Estimate**: 1 hour
**Dependencies**: T005
**Target Milestone**: M3

**Acceptance Tests**:
- Configuration option for rate limit notification level
- Silent mode maintains existing behavior (no notifications)
- Verbose mode includes detailed token usage information
- Default mode shows user-friendly rate limit messages

**Files/Interfaces**:
- `src/tunacode/configuration/key_descriptions.py` (add rate_limit_verbosity)

## Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation | Trigger |
|------|--------|------------|------------|---------|
| RateLimitError parsing fails for different OpenAI versions | High | Medium | Fallback to generic rate limit message | Parsing errors in tests |
| No retry-after header in error response | Medium | Low | Default to 60-second wait time | Missing header in mocked response |
| Countdown display interferes with other UI | Medium | Low | Isolate countdown to dedicated panel area | UI conflicts during testing |
| Users find countdown too verbose | Low | Medium | Make countdown configurable | User feedback during testing |

## Test Strategy
**Single Integration Test**: `tests/test_rate_limit_signaling.py` will mock OpenAI RateLimitError, validate rich panel display with wait time extraction, test countdown integration, and verify resume notification. This focused approach ensures the core rate limit signaling works without over-testing.

## References
- Research: `memory-bank/research/2025-11-20_error_signaling_gaps_analysis.md`
- Rate Limit Prevention: `src/tunacode/configuration/key_descriptions.py:106`
- UI System: `src/tunacode/ui/panels.py`, `src/tunacode/ui/console.py`
- Color Theme: `src/tunacode/constants.py:109-130`
- Countdown Pattern: Existing `_sleep_with_countdown()` implementation

## Final Gate
**Summary**: Focused plan for implementing rate limit error notifications with rich formatting and countdown display.

**Plan Path**: `memory-bank/plan/2025-11-20_rate-limit-signaling-plan.md`
**Milestones**: 3 (Detection → Display → Testing)
**Gates**: 1 integration test validates complete rate limit flow
**Next Command**: `/context-engineer:execute "memory-bank/plan/2025-11-20_rate-limit-signaling-plan.md"`
