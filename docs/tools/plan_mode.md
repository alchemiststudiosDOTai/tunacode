# Plan Mode

Plan mode is a read-only exploration mode where the agent can gather context about the codebase using read-only tools, then present a detailed implementation plan for user approval before executing any write operations.

## Overview

When plan mode is active:
- Write tools (`write_file`, `update_file`) are blocked
- Execute tools (`bash`) are blocked
- Read-only tools remain available for exploration
- The `present_plan` tool becomes available to submit implementation plans

## Activating Plan Mode

Use the `/plan` command to toggle plan mode on/off:

```
/plan
```

When activated, the agent receives instructions about the read-only constraints and available tools.

## Available Tools in Plan Mode

### Read-only Tools (Always Available)
- `read_file` - Read file contents
- `grep` - Search file contents
- `list_dir` - List directory structure
- `glob` - Find files by pattern
- `web_fetch` - Fetch web content
- `react` - ReAct scratchpad for thinking
- `research_codebase` - Delegate research to specialized agent

### Plan-specific Tools
- `present_plan` - Submit implementation plan for approval
- `todowrite` - Track research and planning tasks
- `todoread` - View current task list
- `todoclear` - Clear task list

## The present_plan Tool

The `present_plan` tool is used to submit a detailed implementation plan for user approval.

### Usage

```python
await present_plan(plan_content: str) -> str
```

### Plan Format

Plans should be structured in markdown with these sections:

```markdown
# Implementation Plan: [Brief Title]

## Objective
[1-2 sentence summary of what will be accomplished]

## Files to Modify
- `path/to/file1.py` - [brief change description]
- `path/to/file2.py` - [brief change description]

## Approach
1. [First step with rationale]
2. [Second step with rationale]
3. [Continue as needed]

## Considerations
- [Risk or edge case to handle]
- [Dependencies or prerequisites]

## Acceptance Criteria
- [ ] [Specific, verifiable outcome]
- [ ] [Another verifiable outcome]
```

### Response Handling

When you call `present_plan`:
- If approved: Plan is saved to `PLAN.md`, plan mode exits, and write tools become available
- If denied: You receive feedback to revise your plan and try again

## Authorization System

Plan mode uses a three-tier authorization system:

1. **ALLOW** - Tool executes without confirmation (read-only tools)
2. **CONFIRM** - Tool requires user confirmation (most tools in normal mode)
3. **DENY** - Tool is blocked entirely (write/execute tools in plan mode)

The `PlanModeBlockRule` has the highest priority (100) and blocks write/execute tools when plan mode is active.

## UI Flow

1. User types `/plan` to activate plan mode
2. Agent uses read-only tools to explore and understand the codebase
3. Agent calls `present_plan` with a detailed implementation plan
4. User reviews the plan and either:
   - Approves (plan saved, plan mode exits)
   - Denies (provides feedback for revision)
5. If approved, agent can now use write tools to implement the plan

## Best Practices

1. **Gather sufficient context** before presenting a plan
2. **Be specific** about files to modify and changes to make
3. **Include rationale** for your approach
4. **Consider edge cases** and potential issues
5. **Define clear acceptance criteria** for success

## Example Plan

```markdown
# Implementation Plan: Add User Authentication

## Objective
Implement user authentication system with login/logout functionality and session management.

## Files to Modify
- `src/auth/service.py` - Add authentication service implementation
- `src/auth/models.py` - Add User and Session models
- `src/api/routes.py` - Add authentication endpoints
- `tests/test_auth.py` - Add authentication tests

## Approach
1. Create User and Session models to represent authentication data
2. Implement authentication service with login/logout functionality
3. Add JWT token generation and validation
4. Create API endpoints for authentication flows
5. Add comprehensive test coverage

## Considerations
- Password hashing must use secure algorithm (bcrypt)
- JWT tokens should have appropriate expiration
- Error handling for invalid credentials
- Rate limiting for login attempts

## Acceptance Criteria
- [ ] Users can register new accounts
- [ ] Users can log in with valid credentials
- [ ] Users can log out to invalidate session
- [ ] Invalid credentials are properly rejected
- [ ] All authentication functions have test coverage
```
