---
description: Manage and work on tasks using Task Master MCP tools with integrated scratchpad tracking
allowed-tools: mcp__task-master__*, Bash(llm-agent-tools/scratchpad-multi.sh:*), Read(*), Edit(*), TodoWrite
---

# Workflow Command - Task Master Integration

Efficiently manage and work on tasks using Task Master MCP tools while maintaining work context with scratchpad tracking.

## Current Project Status
- Project Root: (will be determined when running)
- Task Master Status: (will check .taskmaster directory)
- Active Tasks: (will count from tasks.json)

## Process

1. **Initialize or verify Task Master**
   - Check if Task Master is initialized in the project
   - If not, initialize with appropriate settings
   - Verify current task list and status

2. **Select or create task**
   - If task ID provided in $ARGUMENTS, use that task
   - Otherwise, find next available task based on dependencies
   - Show task details including subtasks and complexity

3. **Set up work environment**
   - Mark task as in-progress
   - Initialize scratchpad for this specific task
   - Create TodoWrite list from task subtasks if applicable

4. **Execute task work**
   - Use scratchpad.sh to track progress and thoughts
   - Update task details as work progresses
   - Follow the agent tooling workflow from agent_tools_prompt.xml
   - Maintain context with regular scratchpad updates

5. **Complete task**
   - Update task status when complete
   - Save final scratchpad state
   - Generate summary of work done
   - Update any dependent tasks

## Task Selection
Task to work on: $ARGUMENTS

## Workflow Integration

- Use `llm-agent-tools/scratchpad-multi.sh --agent workflow` for task-specific notes
- Update Task Master task details with key findings
- Sync TodoWrite list with Task Master subtasks
- Follow TDD approach for new features as specified in CLAUDE.md

## Error Handling

- If Task Master not initialized: Offer to initialize
- If no tasks available: Show how to create tasks or parse PRD
- If task blocked: Identify blockers and suggest resolution
- If scratchpad fails: Continue with Task Master only

## Your task
Work on task: $ARGUMENTS
