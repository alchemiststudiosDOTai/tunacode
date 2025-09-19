# ReAct Patterns in AI Agents

ReAct (Reasoning and Acting) patterns in AI agents refer to a framework that combines step-by-step reasoning with action execution to solve complex tasks.

## Core Components

**Reasoning**: The agent analyzes the current situation, breaks down problems, and determines what information or actions are needed next.

**Acting**: The agent executes specific actions (tool calls, API requests, code execution) to gather information or make progress toward the goal.

## Pattern Flow

1. **Thought**: Agent reasons about current state and determines next step
2. **Action**: Agent executes a specific action (tool call, search, etc.)
3. **Observation**: Agent processes results from the action
4. **Repeat**: Cycle continues until goal is achieved

## Key Benefits

- **Transparency**: Each step is explicitly reasoned and documented
- **Error Recovery**: Failed actions can be analyzed and retried with different approaches
- **Adaptability**: Agent can adjust strategy based on intermediate results
- **Verifiability**: Decision-making process is traceable and auditable

## Implementation Example

```
Thought: I need to understand the user's authentication status
Action: Call get_user_session() API
Observation: Session expired, user needs re-authentication
Thought: I should prompt for credentials and retry
Action: Display login form and validate input
```

## Code Pattern

```python
def react_agent_loop(goal: str):
    context = {}
    while not goal_achieved(goal, context):
        # Reasoning step
        thought = reason_about_current_state(goal, context)
        
        # Action step
        action = determine_next_action(thought, context)
        result = execute_action(action)
        
        # Observation step
        context = update_context(context, action, result)
        
    return context
```

This pattern is fundamental to building reliable, explainable AI agents that can handle complex, multi-step tasks while maintaining clear reasoning trails.

## TunaCode Implementation Notes *(tech-docs-maintainer — keep concise)*

- `src/tunacode/tools/react.py` introduces `ReactTool` for recording `think`/`observe` steps against `StateManager.react_scratchpad`.
- Agents register the tool as read-only so sessions can retrieve (`action="get"`) or reset (`action="clear"`) scratchpad state without mutating the workspace.
- Prompt metadata resides in `src/tunacode/tools/prompts/react_prompt.xml` with inline fallbacks to guarantee schema availability.
