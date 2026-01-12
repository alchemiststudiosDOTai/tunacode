"""
Module: tunacode.core.agents.delegation_tools

Delegation tools for multi-agent workflows using pydantic-ai's delegation pattern.
"""

from pydantic_ai import RunContext

from tunacode.core.agents.research_agent import create_research_agent
from tunacode.core.state import StateManager


def create_research_codebase_tool(state_manager: StateManager):
    """Factory to create research_codebase delegation tool with state_manager closure.

    Args:
        state_manager: StateManager instance to access current model and session state

    Returns:
        Async function that delegates research queries to specialized research agent

    Note:
        Progress callback is retrieved from state_manager.session.tool_progress_callback
        at runtime to support dynamic callback updates without agent recreation.
    """

    async def research_codebase(
        ctx: RunContext[None],
        query: str,
        directories: list[str] | None = None,
        max_files: int = 3,
    ) -> dict:
        """Delegate codebase research to specialized read-only agent.

        This tool creates a child agent with read-only tools (grep, glob, list_dir, read_file)
        and delegates research queries to it. The child agent's usage is automatically
        aggregated with the parent agent's usage via ctx.usage.

        Args:
            ctx: RunContext with usage tracking (automatically passed by pydantic-ai)
            query: Research query describing what to find in the codebase
            directories: List of directories to search (defaults to ["."])
            max_files: Maximum number of files to analyze (hard limit: 3, enforced)

        Returns:
            Structured research findings dict with:
                - relevant_files: list of file paths discovered
                - key_findings: list of important discoveries
                - code_examples: relevant code snippets with explanations
                - recommendations: next steps or areas needing attention
        """
        # Enforce hard limit on max_files
        max_files = min(max_files, 3)

        if directories is None:
            directories = ["."]

        # Get current model from session (same model as parent agent)
        model = state_manager.session.current_model

        # Note: Research agent panel display is handled by orchestrator/orchestrator.py
        # which shows a purple panel with query details before execution

        # Get progress callback from session (set at request time by UI)
        progress_callback = state_manager.session.tool_progress_callback

        research_agent = create_research_agent(
            model, state_manager, max_files=max_files, progress_callback=progress_callback
        )

        # Construct research prompt
        prompt = f"""Research the codebase for: {query}

Search in directories: {", ".join(directories)}
Analyze up to {max_files} most relevant files (hard limit: 3 files maximum).

Return a structured summary with:
- relevant_files: list of file paths found
- key_findings: list of important discoveries
- code_examples: relevant code snippets with explanations
- recommendations: next steps or areas needing attention
"""

        # Delegate to research agent with usage propagation
        try:
            result = await research_agent.run(
                prompt,
                usage=ctx.usage,  # Share usage tracking with parent agent
            )

            return result.output

        except Exception as e:
            # Catch all delegation errors (validation failures, pydantic-ai errors, etc.)
            # Return structured error response instead of crashing
            return {
                "error": True,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "relevant_files": [],
                "key_findings": [f"Error during research: {str(e)}"],
                "code_examples": [],
                "recommendations": [
                    "The research agent encountered an error. "
                    "Try simplifying the query or reducing the scope."
                ],
            }

    return research_codebase
