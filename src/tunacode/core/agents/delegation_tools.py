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

        # Show delegation status if streaming panel available
        streaming_panel = getattr(state_manager.session, "streaming_panel", None)
        if streaming_panel:
            dirs_str = ", ".join(directories)
            await streaming_panel.update(
                f"Delegating to research agent...\nQuery: {query}\nDirectories: {dirs_str}"
            )

        # Create research agent with same model as parent
        research_agent = create_research_agent(model, state_manager)

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
        result = await research_agent.run(
            prompt,
            usage=ctx.usage,  # Share usage tracking with parent agent
        )

        if streaming_panel:
            await streaming_panel.update("✓ Research agent completed")

        return result.output

    return research_codebase
