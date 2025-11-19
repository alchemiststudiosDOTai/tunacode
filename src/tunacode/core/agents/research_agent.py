"""Research agent factory for read-only codebase exploration."""

from pathlib import Path

from pydantic_ai import Agent, Tool
from pydantic_ai.exceptions import UserError

from tunacode.core.state import StateManager
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.types import ModelName


def _load_research_prompt() -> str:
    """Load research-specific system prompt from prompts/research/system.xml.

    Returns:
        Research system prompt content

    Raises:
        FileNotFoundError: If system.xml does not exist in prompts/research directory
    """
    # Navigate from this file: core/agents/research_agent.py -> src/tunacode/prompts/research
    base_path = Path(__file__).parent.parent.parent
    prompts_dir = base_path / "prompts" / "research"
    prompt_path = prompts_dir / "system.xml"

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Required research prompt file not found: {prompt_path}. "
            "The system.xml file must exist in the prompts/research directory."
        )

    return prompt_path.read_text(encoding="utf-8").strip()


def _create_limited_read_file(max_files: int):
    """Create a read_file wrapper that enforces a maximum number of calls.

    Args:
        max_files: Maximum number of files that can be read

    Returns:
        Wrapped read_file function with call limit enforcement
    """
    call_count = {"count": 0}

    async def limited_read_file(file_path: str) -> dict:
        """Read file with enforced limit on number of calls.

        Args:
            file_path: Path to file to read

        Returns:
            File content dict from read_file tool

        Raises:
            UserError: If max_files limit has been reached
        """
        if call_count["count"] >= max_files:
            raise UserError(
                f"Maximum file read limit reached ({max_files} files). "
                "Cannot read more files in this research task."
            )

        call_count["count"] += 1
        return await read_file(file_path)

    return limited_read_file


def create_research_agent(
    model: ModelName, state_manager: StateManager, max_files: int = 3
) -> Agent:
    """Create research agent with read-only tools and file read limit.

    IMPORTANT: Uses same model as main agent - do NOT hardcode model selection.

    Args:
        model: The model name to use (same as main agent)
        state_manager: State manager for session context
        max_files: Maximum number of files the agent can read (hard limit, default: 3)

    Returns:
        Agent configured with read-only tools, research system prompt, and file limit
    """
    # Load research-specific system prompt
    system_prompt = _load_research_prompt()

    # Get configuration from state manager
    max_retries = state_manager.session.user_config.get("settings", {}).get("max_retries", 3)
    tool_strict_validation = state_manager.session.user_config.get("settings", {}).get(
        "tool_strict_validation", False
    )

    # Create limited read_file tool that enforces max_files cap
    limited_read_file = _create_limited_read_file(max_files)

    # Create read-only tools list (no write/execute capabilities)
    tools_list = [
        Tool(limited_read_file, max_retries=max_retries, strict=tool_strict_validation),
        Tool(grep, max_retries=max_retries, strict=tool_strict_validation),
        Tool(list_dir, max_retries=max_retries, strict=tool_strict_validation),
        Tool(glob, max_retries=max_retries, strict=tool_strict_validation),
    ]

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools_list,
        output_type=dict,  # Structured research output as JSON dict
    )
