"""Research agent factory for read-only codebase exploration."""

from pathlib import Path

from httpx import AsyncClient, HTTPStatusError
from pydantic_ai import Agent, Tool
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from tenacity import retry_if_exception_type, stop_after_attempt

from tunacode.core.prompting import (
    RESEARCH_TEMPLATE,
    SectionLoader,
    SystemPromptSection,
    compose_prompt,
    resolve_prompt,
)
from tunacode.core.state import StateManager
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.types import ModelName

# Maximum wait time in seconds for retry backoff
MAX_RETRY_WAIT_SECONDS = 60


def _load_research_prompt() -> str:
    """Load research-specific system prompt with section-based composition.

    Loads individual section files from prompts/research/sections/ and
    composes them using RESEARCH_TEMPLATE.

    Returns:
        Research system prompt content

    Raises:
        FileNotFoundError: If prompts/research/sections/ does not exist
    """
    # Navigate from this file: core/agents/research_agent.py -> src/tunacode/prompts/research
    base_path = Path(__file__).parent.parent.parent
    prompts_dir = base_path / "prompts" / "research"
    sections_dir = prompts_dir / "sections"

    if not sections_dir.exists():
        raise FileNotFoundError(
            f"Required sections directory not found: {sections_dir}. "
            "The prompts/research/sections/ directory must exist."
        )

    loader = SectionLoader(sections_dir)
    sections = {s.value: loader.load_section(s) for s in SystemPromptSection}

    # Compose sections into research template, then resolve dynamic placeholders
    prompt = compose_prompt(RESEARCH_TEMPLATE, sections)
    return resolve_prompt(prompt)


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
            File content dict from read_file tool, or limit message if exceeded

        Note:
            Returns a warning message instead of raising error when limit reached,
            allowing the agent to complete with partial results.
        """
        if call_count["count"] >= max_files:
            return {
                "content": f"FILE READ LIMIT REACHED ({max_files} files maximum)\n\n"
                f"Cannot read '{file_path}' - you have already read {max_files} files.\n"
                "Please complete your research with the files you have analyzed.",
                "lines": 0,
                "size": 0,
            }

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

    # Import here to avoid circular import with agent_config.py
    # (agent_config imports delegation_tools which imports this module)
    from tunacode.core.agents.agent_components.agent_config import (
        _build_request_hooks,
        _coerce_request_delay,
        _create_model_with_retry,
    )

    transport = AsyncTenacityTransport(
        config=RetryConfig(
            retry=retry_if_exception_type(HTTPStatusError),
            wait=wait_retry_after(max_wait=MAX_RETRY_WAIT_SECONDS),
            stop=stop_after_attempt(max_retries),
            reraise=True,
        ),
        validate_response=lambda r: r.raise_for_status(),
    )
    request_delay = _coerce_request_delay(state_manager)
    event_hooks = _build_request_hooks(request_delay, state_manager)
    http_client = AsyncClient(transport=transport, event_hooks=event_hooks)

    model_instance = _create_model_with_retry(model, http_client, state_manager)

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
        model=model_instance,
        system_prompt=system_prompt,
        tools=tools_list,
        output_type=dict,  # Structured research output as JSON dict
    )
