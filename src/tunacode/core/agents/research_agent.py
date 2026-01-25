"""Research agent factory for read-only codebase exploration."""

import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from httpx import AsyncClient, HTTPStatusError
from pydantic_ai import Agent, Tool
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from tenacity import retry_if_exception_type, stop_after_attempt

from tunacode.core.logging import get_logger
from tunacode.core.prompting import (
    RESEARCH_TEMPLATE,
    SectionLoader,
    SystemPromptSection,
    compose_prompt,
    resolve_prompt,
)
from tunacode.core.state import StateManager
from tunacode.tools.decorators import file_tool
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.types import ModelName, ToolProgress, ToolProgressCallback

# Maximum wait time in seconds for retry backoff
# move this to the defualt config TODO, for now let it pass, but handle this in its own pr
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


def _create_limited_read_file(max_files: int) -> Callable[[str], Awaitable[str]]:
    """Create a read_file wrapper that enforces a maximum number of calls.

    Args:
        max_files: Maximum number of files that can be read

    Returns:
        Wrapped read_file function with call limit enforcement
    """
    logger = get_logger()
    call_count = {"count": 0}

    @file_tool
    async def limited_read_file(filepath: str) -> str:
        """Read file with enforced limit on number of calls.

        Args:
            filepath: Path to file to read

        Returns:
            File content dict from read_file tool, or limit message if exceeded

        Note:
            Returns a warning message instead of raising error when limit reached,
            allowing the agent to complete with partial results.
        """
        if call_count["count"] >= max_files:
            logger.warning(f"Research agent file limit reached ({max_files})")
            return (
                "<file>\n"
                f"FILE READ LIMIT REACHED ({max_files} files maximum)\n\n"
                f"Cannot read '{filepath}' - you have already read {max_files} files.\n"
                "Please complete your research with the files you have analyzed.\n"
                "</file>"
            )

        call_count["count"] += 1
        return await read_file(filepath)

    return limited_read_file


# todo move this to be properly imported and modular TODO
class ProgressTracker:
    """Tracks tool execution progress for subagent feedback.

    Note: total_operations is always 0 (unknown) since the number of
    tool calls cannot be predicted upfront.
    """

    def __init__(self, callback: ToolProgressCallback | None, subagent_name: str = "research"):
        self.callback = callback
        self.subagent_name = subagent_name
        self.operation_count = 0
        self.total_operations = 0  # Always 0: total is unknown upfront

    def emit(self, operation: str) -> None:
        """Emit progress event for current operation."""
        self.operation_count += 1
        if self.callback:
            progress = ToolProgress(
                subagent=self.subagent_name,
                operation=operation,
                current=self.operation_count,
                total=self.total_operations,
            )
            self.callback(progress)

    def wrap_tool(
        self, tool_func: Callable[..., Awaitable[Any]], tool_name: str
    ) -> Callable[..., Awaitable[Any]]:
        """Wrap a tool function to emit progress before execution."""

        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            # Format operation description
            if args:
                first_arg = str(args[0])[:40]
                operation = f"{tool_name} {first_arg}"
            elif kwargs:
                first_val = str(next(iter(kwargs.values())))[:40]
                operation = f"{tool_name} {first_val}"
            else:
                operation = tool_name

            self.emit(operation)
            return await tool_func(*args, **kwargs)

        # Preserve function metadata for pydantic-ai schema generation
        wrapped.__name__ = tool_func.__name__
        wrapped.__doc__ = tool_func.__doc__
        wrapped.__annotations__ = getattr(tool_func, "__annotations__", {})
        wrapped.__signature__ = inspect.signature(tool_func)  # type: ignore[attr-defined]

        return wrapped


def create_research_agent(
    model: ModelName,
    state_manager: StateManager,
    max_files: int = 3,
    progress_callback: ToolProgressCallback | None = None,
) -> Agent[None, str]:
    """Create research agent with read-only tools and file read limit.

    IMPORTANT: Uses same model as main agent - do NOT hardcode model selection.

    Args:
        model: The model name to use (same as main agent)
        state_manager: State manager for session context
        max_files: Maximum number of files the agent can read (hard limit, default: 3)
        progress_callback: Optional callback for tool execution progress updates

    Returns:
        Agent configured with read-only tools, research system prompt, and file limit
    """
    logger = get_logger()

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
    event_hooks = _build_request_hooks(request_delay)
    http_client = AsyncClient(transport=transport, event_hooks=event_hooks)

    model_instance = _create_model_with_retry(model, http_client, state_manager)

    # Create limited read_file tool that enforces max_files cap
    limited_read_file = _create_limited_read_file(max_files)

    # Set up progress tracking if callback provided
    tracker = ProgressTracker(progress_callback, "research")

    # Wrap tools with progress tracking
    if progress_callback:
        tracked_read_file = tracker.wrap_tool(limited_read_file, "read_file")
        tracked_grep = tracker.wrap_tool(grep, "grep")
        tracked_list_dir = tracker.wrap_tool(list_dir, "list_dir")
        tracked_glob = tracker.wrap_tool(glob, "glob")
    else:
        tracked_read_file = limited_read_file
        tracked_grep = grep
        tracked_list_dir = list_dir
        tracked_glob = glob

    # Create read-only tools list (no write/execute capabilities)
    tools_list = [
        Tool(tracked_read_file, max_retries=max_retries, strict=tool_strict_validation),
        Tool(tracked_grep, max_retries=max_retries, strict=tool_strict_validation),
        Tool(tracked_list_dir, max_retries=max_retries, strict=tool_strict_validation),
        Tool(tracked_glob, max_retries=max_retries, strict=tool_strict_validation),
    ]

    logger.debug(f"Research agent created: {model} (max_files={max_files})")

    return Agent(
        model=model_instance,
        system_prompt=system_prompt,
        tools=tools_list,
        # Note: Agent returns str by default. Caller parses JSON response.
    )
