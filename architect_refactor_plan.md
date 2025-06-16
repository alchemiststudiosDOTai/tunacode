### Problem Description
*   The current `/architect` mode is not synchronized with the core agent's capabilities, leading to divergent behavior and performance issues.
*   It operates as a "black box," generating a complete plan upfront and executing it without the ability to adapt to the outcome of intermediate steps. This contrasts with the regular agent's more interactive, step-by-step nature.
*   The core deficiency is the lack of a ReAct (Reason, Act) feedback loop, which prevents the planner from correcting its course or handling unexpected results during execution.

### Solution Overview
*   Refactor `/architect` mode to use a new, adaptive `ReActAgent`.
*   This agent will combine the long-term planning of the original architect with the iterative, observation-based execution logic of a ReAct framework.
*   The solution involves updating the planner, introducing a dedicated tool handler, and implementing a core ReAct loop to manage state and execution flow.

### Implementation Details
1.  **Update Planner Schema:**
    *   Modify `<src/tunacode/core/agents/planner_schema.py>`.
    *   Enhance the `Task` model to include `tool: str` and `args: Dict[str, Any]` fields, making it a self-contained, executable unit.

2.  **Implement the ReAct Agent:**
    *   Create a new file: `<src/tunacode/core/agents/react_agent.py>`.
    *   Define a `ReActAgent` class within this file to encapsulate the new logic.
    *   This class will manage the execution of the task plan.

3.  **Create a Tool Handler:**
    *   Create a new file: `<src/tunacode/core/tool_handler.py>`.
    *   Implement a `ToolHandler` class responsible for dynamically invoking the correct tool (e.g., `read_file`, `grep`, `update_file`) based on the `tool` field in a given `Task`.

4.  **Update Orchestrator:**
    *   Modify `<src/tunacode/core/agents/orchestrator.py>`.
    *   Replace the existing task execution logic with calls to the new `ReActAgent`.
    *   The `OrchestratorAgent`'s role will shift to primarily invoking the `ReActAgent` and handling the final results.

5.  **Refine Architect Prompt:**
    *   Update `<src/tunacode/prompts/architect_planner.md>`.
    *   Ensure the prompt instructs the LLM to generate a plan that strictly conforms to the updated `planner_schema.py`, including the new `tool` and `args` fields for every task.

### Technical Flow
1.  A user request in `/architect` mode is routed to the `OrchestratorAgent`.
2.  The `OrchestratorAgent` invokes the `ReActAgent` with the user's request.
3.  The `ReActAgent` calls the planner LLM (using the refined prompt) to generate a full `Plan` object, consisting of a list of `Task` objects.
4.  The `ReActAgent` iterates through the list of `Task` objects in the plan:
    *   For each `Task`, it passes the task to the `ToolHandler`.
    *   The `ToolHandler` executes the specified `tool` with the provided `args`.
    *   The output (observation) from the tool is captured.
5.  The `ReActAgent` accumulates results from each step and, upon completion, returns a final, comprehensive response to the user.

### Testing Guide
1.  Develop unit tests for the `ReActAgent` to verify its core loop and state management.
2.  Create unit tests for the `ToolHandler` to ensure it correctly dispatches to and executes all available tools.
3.  Write integration tests that simulate a full user request through the `/architect` command to validate the end-to-end flow, from planning to final output.
4.  Test edge cases, including plans with failing steps and empty plans, to ensure the system fails gracefully and provides informative error messages.