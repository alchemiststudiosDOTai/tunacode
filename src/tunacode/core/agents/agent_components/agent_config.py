"""Agent configuration and creation utilities."""

from pathlib import Path
from typing import Dict, Tuple

from httpx import AsyncClient, HTTPStatusError
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig, wait_retry_after
from tenacity import retry_if_exception_type, stop_after_attempt

from tunacode.core.logging.logger import get_logger
from tunacode.core.state import StateManager
from tunacode.services.mcp import get_mcp_servers, register_mcp_agent
from tunacode.tools.bash import bash
from tunacode.tools.glob import glob
from tunacode.tools.grep import grep
from tunacode.tools.list_dir import list_dir
from tunacode.tools.read_file import read_file
from tunacode.tools.run_command import run_command
from tunacode.tools.update_file import update_file
from tunacode.tools.write_file import write_file
from tunacode.types import ModelName, PydanticAgent

logger = get_logger(__name__)

# Module-level caches for system prompts
_PROMPT_CACHE: Dict[str, Tuple[str, float]] = {}
_TUNACODE_CACHE: Dict[str, Tuple[str, float]] = {}

# Module-level cache for agents to persist across requests
_AGENT_CACHE: Dict[ModelName, PydanticAgent] = {}
_AGENT_CACHE_VERSION: Dict[ModelName, int] = {}



def clear_all_caches():
    """Clear all module-level caches. Useful for testing."""
    _PROMPT_CACHE.clear()
    _TUNACODE_CACHE.clear()
    _AGENT_CACHE.clear()
    _AGENT_CACHE_VERSION.clear()


def get_agent_tool():
    """Lazy import for Agent and Tool to avoid circular imports."""
    from pydantic_ai import Tool

    return Agent, Tool


def _read_prompt_from_path(prompt_path: Path) -> str:
    """Return prompt content from disk, leveraging the cache when possible."""
    cache_key = str(prompt_path)

    try:
        current_mtime = prompt_path.stat().st_mtime
    except FileNotFoundError as error:
        raise FileNotFoundError from error

    if cache_key in _PROMPT_CACHE:
        cached_content, cached_mtime = _PROMPT_CACHE[cache_key]
        if current_mtime == cached_mtime:
            return cached_content

    try:
        content = prompt_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise FileNotFoundError from error

    _PROMPT_CACHE[cache_key] = (content, current_mtime)
    return content


def load_system_prompt(base_path: Path) -> str:
    """Load the system prompt from system.xml file with caching.
    
    Raises:
        FileNotFoundError: If system.xml does not exist in the prompts directory.
    """
    prompts_dir = base_path / "prompts"
    prompt_path = prompts_dir / "system.xml"

    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Required system prompt file not found: {prompt_path}. "
            "The system.xml file must exist in the prompts directory."
        )

    return _read_prompt_from_path(prompt_path)


def load_tunacode_context() -> str:
    """Load AGENTS.md context if it exists with caching."""
    try:
        tunacode_path = Path.cwd() / "AGENTS.md"
        cache_key = str(tunacode_path)

        if not tunacode_path.exists():
            logger.info("📄 AGENTS.md not found: Using default context")
            return ""

        # Check cache with file modification time
        if cache_key in _TUNACODE_CACHE:
            cached_content, cached_mtime = _TUNACODE_CACHE[cache_key]
            current_mtime = tunacode_path.stat().st_mtime
            if current_mtime == cached_mtime:
                return cached_content

        # Load from file and cache
        tunacode_content = tunacode_path.read_text(encoding="utf-8")
        if tunacode_content.strip():
            logger.info("📄 AGENTS.md located: Loading context...")
            result = "\n\n# Project Context from AGENTS.md\n" + tunacode_content
            _TUNACODE_CACHE[cache_key] = (result, tunacode_path.stat().st_mtime)
            return result
        else:
            logger.info("📄 AGENTS.md not found: Using default context")
            _TUNACODE_CACHE[cache_key] = ("", tunacode_path.stat().st_mtime)
            return ""

    except Exception as e:
        logger.debug(f"Error loading AGENTS.md: {e}")
        return ""


def _create_model_with_retry(
    model_string: str, http_client: AsyncClient, state_manager: StateManager
):
    """Create a model instance with retry-enabled HTTP client.

    Parses model string in format 'provider:model_name' and creates
    appropriate provider and model instances with the retry-enabled HTTP client.
    """
    # Extract environment config
    env = state_manager.session.user_config.get("env", {})

    # Provider configuration: API key names and base URLs
    PROVIDER_CONFIG = {
        "anthropic": {"api_key_name": "ANTHROPIC_API_KEY", "base_url": None},
        "openai": {"api_key_name": "OPENAI_API_KEY", "base_url": None},
        "openrouter": {
            "api_key_name": "OPENROUTER_API_KEY",
            "base_url": "https://openrouter.ai/api/v1",
        },
        "azure": {
            "api_key_name": "AZURE_OPENAI_API_KEY",
            "base_url": env.get("AZURE_OPENAI_ENDPOINT"),
        },
        "deepseek": {"api_key_name": "DEEPSEEK_API_KEY", "base_url": None},
    }

    # Parse model string
    if ":" in model_string:
        provider_name, model_name = model_string.split(":", 1)
    else:
        # Auto-detect provider from model name
        model_name = model_string
        if model_name.startswith("claude"):
            provider_name = "anthropic"
        elif model_name.startswith(("gpt", "o1", "o3")):
            provider_name = "openai"
        else:
            # Default to treating as model string (pydantic-ai will auto-detect)
            return model_string

    # Create provider with api_key + base_url + http_client
    if provider_name == "anthropic":
        api_key = env.get("ANTHROPIC_API_KEY")
        provider = AnthropicProvider(api_key=api_key, http_client=http_client)
        return AnthropicModel(model_name, provider=provider)
    elif provider_name in ("openai", "openrouter", "azure", "deepseek"):
        # OpenAI-compatible providers all use OpenAIChatModel
        config = PROVIDER_CONFIG.get(provider_name, {})
        api_key = env.get(config.get("api_key_name"))
        base_url = config.get("base_url")
        provider = OpenAIProvider(api_key=api_key, base_url=base_url, http_client=http_client)
        return OpenAIChatModel(model_name, provider=provider)
    else:
        # Unsupported provider, return string and let pydantic-ai handle it
        # (won't have retry support but won't break)
        logger.warning(
            f"Provider '{provider_name}' not configured for HTTP retries. "
            f"Falling back to default behavior."
        )
        return model_string


def get_or_create_agent(model: ModelName, state_manager: StateManager) -> PydanticAgent:
    """Get existing agent or create new one for the specified model."""
    import logging

    logger = logging.getLogger(__name__)

    # Check session-level cache first (for backward compatibility with tests)
    if model in state_manager.session.agents:
        logger.debug(f"Using session-cached agent for model {model}")
        return state_manager.session.agents[model]

    # Check module-level cache
    if model in _AGENT_CACHE:
        # Verify cache is still valid (check for config changes)
        settings = state_manager.session.user_config.get("settings", {})
        current_version = hash(
            (
                str(settings.get("max_retries", 3)),
                str(settings.get("tool_strict_validation", False)),
                str(state_manager.session.user_config.get("mcpServers", {})),
            )
        )
        if _AGENT_CACHE_VERSION.get(model) == current_version:
            logger.debug(f"Using module-cached agent for model {model}")
            state_manager.session.agents[model] = _AGENT_CACHE[model]
            return _AGENT_CACHE[model]
        else:
            logger.debug(f"Cache invalidated for model {model} due to config change")
            del _AGENT_CACHE[model]
            del _AGENT_CACHE_VERSION[model]

    if model not in _AGENT_CACHE:
        logger.debug(f"Creating new agent for model {model}")
        max_retries = state_manager.session.user_config.get("settings", {}).get("max_retries", 3)

        # Lazy import Agent and Tool
        Agent, Tool = get_agent_tool()

        # Load system prompt
        base_path = Path(__file__).parent.parent.parent.parent
        system_prompt = load_system_prompt(base_path)

        # Load AGENTS.md context
        # IMPORTANT: Injects project workflow rules and optimization mandates from
        # AGENTS.md directly into the agent's system prompt.
        # This makes all agent behavior a product of the repository's latest
        # coding/testing/documentation standards.
        system_prompt += load_tunacode_context()

        # Get tool strict validation setting from config (default to False for backward
        # compatibility)
        tool_strict_validation = state_manager.session.user_config.get("settings", {}).get(
            "tool_strict_validation", False
        )

        # Create tool list
        tools_list = [
            Tool(bash, max_retries=max_retries, strict=tool_strict_validation),
            Tool(glob, max_retries=max_retries, strict=tool_strict_validation),
            Tool(grep, max_retries=max_retries, strict=tool_strict_validation),
            Tool(list_dir, max_retries=max_retries, strict=tool_strict_validation),
            Tool(read_file, max_retries=max_retries, strict=tool_strict_validation),
            Tool(run_command, max_retries=max_retries, strict=tool_strict_validation),
            Tool(update_file, max_retries=max_retries, strict=tool_strict_validation),
            Tool(write_file, max_retries=max_retries, strict=tool_strict_validation),
        ]

        logger.debug(f"Creating agent with {len(tools_list)} tools")

        mcp_servers = get_mcp_servers(state_manager)

        # Configure HTTP client with retry logic at transport layer
        # This handles retries BEFORE node creation, avoiding pydantic-ai's
        # single-stream-per-node constraint violations
        # https://ai.pydantic.dev/api/retries/#pydantic_ai.retries.wait_retry_after
        transport = AsyncTenacityTransport(
            config=RetryConfig(
                retry=retry_if_exception_type(HTTPStatusError),
                wait=wait_retry_after(max_wait=60),
                stop=stop_after_attempt(max_retries),
                reraise=True,
            ),
            validate_response=lambda r: r.raise_for_status(),
        )
        http_client = AsyncClient(transport=transport)

        # Create model instance with retry-enabled HTTP client
        model_instance = _create_model_with_retry(model, http_client, state_manager)

        agent = Agent(
            model=model_instance,
            system_prompt=system_prompt,
            tools=tools_list,
            mcp_servers=mcp_servers,
        )

        # Register agent for MCP cleanup tracking
        mcp_server_names = state_manager.session.user_config.get("mcpServers", {}).keys()
        for server_name in mcp_server_names:
            register_mcp_agent(server_name, agent)

        # Store in both caches
        _AGENT_CACHE[model] = agent
        _AGENT_CACHE_VERSION[model] = hash(
            (
                str(state_manager.session.user_config.get("settings", {}).get("max_retries", 3)),
                str(
                    state_manager.session.user_config.get("settings", {}).get(
                        "tool_strict_validation", False
                    )
                ),
                str(state_manager.session.user_config.get("mcpServers", {})),
            )
        )
        state_manager.session.agents[model] = agent

    return _AGENT_CACHE[model]
