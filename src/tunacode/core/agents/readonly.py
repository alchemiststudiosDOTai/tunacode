"""Read-only agent implementation for non-mutating operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...tools.bash import bash
from ...tools.grep import grep
from ...tools.list_dir import list_dir
from ...tools.read_file import read_file
from ...types import AgentRun, ModelName, ResponseState
from ..state import StateManager

if TYPE_CHECKING:
    from ...types import PydanticAgent


class ReadOnlyAgent:
    """Agent configured with read-only tools for analysis tasks."""

    def __init__(self, model: ModelName, state_manager: StateManager):
        self.model = model
        self.state_manager = state_manager
        self._agent: PydanticAgent | None = None

    def _get_agent(self) -> PydanticAgent:
        """Lazily create the agent with read-only tools."""
        if self._agent is None:
            from .main import get_agent_tool

            Agent, Tool = get_agent_tool()

            # Create agent with only read-only tools
            self._agent = Agent(
                model=self.model,
                system_prompt=(
                    "You are a read-only assistant. You can analyze and read files but cannot modify them. "
                    "You can also execute shell commands for inspection purposes. When listing directories, "
                    "prefer using list_dir over bash ls commands."
                ),
                tools=[
                    Tool(read_file),
                    Tool(grep),
                    Tool(list_dir),
                    Tool(bash),
                ],
            )
        return self._agent

    async def process_request(self, request: str) -> AgentRun:
        """Process a request using only read-only tools."""
        from rich.console import Console
        console = Console()
        
        console.print(f"[yellow][DEBUG][/yellow] Starting read-only request: {request}")
        agent = self._get_agent()
        response_state = ResponseState()

        last_node_with_output = None
        node_count = 0

        # Use iter() like main.py does to get the full run context
        async with agent.iter(request) as agent_run:
            async for node in agent_run:
                node_count += 1
                console.print(f"[yellow][DEBUG][/yellow] Processing node #{node_count}")
                
                # Check if this node produced user-visible output
                if hasattr(node, "result") and node.result and hasattr(node.result, "output"):
                    if node.result.output:
                        console.print(f"[yellow][DEBUG][/yellow] Found node with output: {node.result.output[:100]}...")
                        response_state.has_user_response = True
                        last_node_with_output = node
                    else:
                        console.print("[yellow][DEBUG][/yellow] Node has result but empty output")
                else:
                    console.print("[yellow][DEBUG][/yellow] Node has no result or output attribute")

        console.print(f"[yellow][DEBUG][/yellow] Processed {node_count} nodes")
        console.print(f"[yellow][DEBUG][/yellow] Last node with output: {'Found' if last_node_with_output else 'None'}")

        # If we found a node with output, return it (with response_state)
        if last_node_with_output is not None:
            console.print("[yellow][DEBUG][/yellow] Returning node with output")
            # Attach response_state for compatibility
            last_node_with_output.response_state = response_state
            return last_node_with_output

        console.print("[yellow][DEBUG][/yellow] No output node found, returning wrapped agent run")
        # Fallback: Wrap the agent run to include response_state
        class AgentRunWithState:
            def __init__(self, wrapped_run):
                self._wrapped = wrapped_run
                self.response_state = response_state

            def __getattr__(self, name):
                # Delegate all other attributes to the wrapped object
                return getattr(self._wrapped, name)

        return AgentRunWithState(agent_run)
