# ReAct Shim Component Overview

## Purpose
Implements a ReAct (Reasoning + Acting) feedback loop that guides the main agent through iterative planning and evaluation.

## Key Components

### ReactCoordinator (main.py:220-404)
- **Role**: Orchestrates planner/evaluator feedback loop
- **Key Methods**: `bootstrap()`, `observe_step()`, `_generate_plan()`, `_evaluate_step()`
- **Integration**: Embedded in `process_request()` to provide real-time guidance

### React Agents (agent_config.py:56-103)
- **Planner**: Proposes next actionable steps based on feedback
- **Evaluator**: Assesses if observations satisfy user query
- **Caching**: Module-level cache with version invalidation

## Constants
- `REACT_MAX_STEPS`: 4 (maximum planner/evaluator cycles)
- `UNPRODUCTIVE_LIMIT`: 3 (iterations without tool use before forcing action)

## Cache Strategy
- React agents cached separately from main agent
- Version hash includes plan mode, max_retries, and react_prompt_version
- Automatic cache invalidation on config changes

## Integration Points
- `process_request()`: Main integration point
- `get_react_agents()`: Agent provisioning
- State management through `StateFacade`

## Behavior
- Provides step-by-step guidance messages
- Enables graceful degradation when agents fail
- Respects iteration limits and completion signals
