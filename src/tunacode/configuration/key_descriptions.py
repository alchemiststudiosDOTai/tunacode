"""
Module: tunacode.configuration.key_descriptions

Educational descriptions and examples for configuration keys to help users
understand what each setting does and how to configure it properly.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class KeyDescription:
    """Description of a configuration key with examples and help text."""

    name: str
    description: str
    example: Any
    help_text: str
    category: str
    is_sensitive: bool = False
    service_type: Optional[str] = None  # For API keys: "openai", "anthropic", etc.


# Configuration key descriptions organized by category
CONFIG_KEY_DESCRIPTIONS: Dict[str, KeyDescription] = {
    # Root level keys
    "default_model": KeyDescription(
        name="default_model",
        description="Which AI model TunaCode uses by default",
        example="openrouter:openai/gpt-4.1",
        help_text="Format: provider:model-name. Examples: openai:gpt-4, anthropic:claude-3-sonnet, google:gemini-pro",
        category="AI Models",
    ),
    # Environment variables (API Keys)
    "env.OPENAI_API_KEY": KeyDescription(
        name="OPENAI_API_KEY",
        description="Your OpenAI API key for GPT models",
        example="sk-proj-abc123...",
        help_text="Get this from https://platform.openai.com/api-keys. Required for OpenAI models like GPT-4.",
        category="API Keys",
        is_sensitive=True,
        service_type="openai",
    ),
    "env.ANTHROPIC_API_KEY": KeyDescription(
        name="ANTHROPIC_API_KEY",
        description="Your Anthropic API key for Claude models",
        example="sk-ant-api03-abc123...",
        help_text="Get this from https://console.anthropic.com/. Required for Claude models.",
        category="API Keys",
        is_sensitive=True,
        service_type="anthropic",
    ),
    "env.OPENROUTER_API_KEY": KeyDescription(
        name="OPENROUTER_API_KEY",
        description="Your OpenRouter API key for accessing multiple models",
        example="sk-or-v1-abc123...",
        help_text="Get this from https://openrouter.ai/keys. Gives access to many different AI models.",
        category="API Keys",
        is_sensitive=True,
        service_type="openrouter",
    ),
    "env.GEMINI_API_KEY": KeyDescription(
        name="GEMINI_API_KEY",
        description="Your Google Gemini API key",
        example="AIza123...",
        help_text="Get this from Google AI Studio. Required for Gemini models.",
        category="API Keys",
        is_sensitive=True,
        service_type="google",
    ),
    "env.OPENAI_BASE_URL": KeyDescription(
        name="OPENAI_BASE_URL",
        description="Custom API endpoint for OpenAI-compatible services",
        example="https://api.cerebras.ai/v1",
        help_text="Use this to connect to local models (LM Studio, Ollama) or alternative providers like Cerebras.",
        category="API Configuration",
    ),
    # Settings
    "settings.max_retries": KeyDescription(
        name="max_retries",
        description="How many times to retry failed API calls",
        example=10,
        help_text="Higher values = more resilient to temporary API issues, but slower when APIs are down.",
        category="Behavior Settings",
    ),
    "settings.max_iterations": KeyDescription(
        name="max_iterations",
        description="Maximum conversation turns before stopping",
        example=40,
        help_text="Prevents infinite loops. TunaCode will stop after this many back-and-forth exchanges.",
        category="Behavior Settings",
    ),
    "settings.tool_ignore": KeyDescription(
        name="tool_ignore",
        description="List of tools TunaCode should not use",
        example=["read_file", "write_file"],
        help_text="Useful for restricting what TunaCode can do. Empty list means all tools are available.",
        category="Tool Configuration",
    ),
    "settings.guide_file": KeyDescription(
        name="guide_file",
        description="Name of your project guide file",
        example="AGENTS.md",
        help_text="TunaCode looks for this file to understand your project. Usually AGENTS.md or README.md.",
        category="Project Settings",
    ),
    "settings.fallback_response": KeyDescription(
        name="fallback_response",
        description="Whether to provide a response when tools fail",
        example=True,
        help_text="When true, TunaCode will try to help even if some tools don't work properly.",
        category="Behavior Settings",
    ),
    "settings.fallback_verbosity": KeyDescription(
        name="fallback_verbosity",
        description="How detailed fallback responses should be",
        example="normal",
        help_text="Options: minimal, normal, detailed. Controls how much TunaCode explains when things go wrong.",
        category="Behavior Settings",
    ),
    "settings.context_window_size": KeyDescription(
        name="context_window_size",
        description="Maximum tokens TunaCode can use in one conversation",
        example=200000,
        help_text="Larger values = TunaCode remembers more context, but costs more. Adjust based on your model's limits.",
        category="Performance Settings",
    ),
    "settings.enable_streaming": KeyDescription(
        name="enable_streaming",
        description="Show AI responses as they're generated",
        example=True,
        help_text="When true, you see responses appear word-by-word. When false, you wait for complete responses.",
        category="User Experience",
    ),
    # Ripgrep settings
    "settings.ripgrep.use_bundled": KeyDescription(
        name="ripgrep.use_bundled",
        description="Use TunaCode's built-in ripgrep instead of system version",
        example=False,
        help_text="Usually false is better - uses your system's ripgrep which may be newer/faster.",
        category="Search Settings",
    ),
    "settings.ripgrep.timeout": KeyDescription(
        name="ripgrep.timeout",
        description="How long to wait for search results (seconds)",
        example=10,
        help_text="Prevents searches from hanging. Increase for very large codebases.",
        category="Search Settings",
    ),
    "settings.ripgrep.max_buffer_size": KeyDescription(
        name="ripgrep.max_buffer_size",
        description="Maximum size of search results (bytes)",
        example=1048576,
        help_text="1MB by default. Prevents memory issues with huge search results.",
        category="Search Settings",
    ),
    "settings.ripgrep.max_results": KeyDescription(
        name="ripgrep.max_results",
        description="Maximum number of search results to return",
        example=100,
        help_text="Prevents overwhelming output. Increase if you need more comprehensive search results.",
        category="Search Settings",
    ),
    "settings.ripgrep.enable_metrics": KeyDescription(
        name="ripgrep.enable_metrics",
        description="Collect performance data about searches",
        example=False,
        help_text="Enable for debugging search performance. Usually not needed.",
        category="Search Settings",
    ),
    "settings.ripgrep.debug": KeyDescription(
        name="ripgrep.debug",
        description="Show detailed search debugging information",
        example=False,
        help_text="Enable for troubleshooting search issues. Creates verbose output.",
        category="Search Settings",
    ),
    # Tutorial/onboarding settings
    "settings.enable_tutorial": KeyDescription(
        name="enable_tutorial",
        description="Show tutorial prompts for new users",
        example=True,
        help_text="Helps new users learn TunaCode. Disable once you're comfortable with the tool.",
        category="User Experience",
    ),
    "settings.first_installation_date": KeyDescription(
        name="first_installation_date",
        description="When TunaCode was first installed",
        example="2025-09-11T11:50:40.167105",
        help_text="Automatically set. Used for tracking usage patterns and showing relevant tips.",
        category="System Information",
    ),
    "settings.tutorial_declined": KeyDescription(
        name="tutorial_declined",
        description="Whether user declined the tutorial",
        example=True,
        help_text="Automatically set when you skip the tutorial. Prevents repeated tutorial prompts.",
        category="User Experience",
    ),
    # MCP Servers
    "mcpServers": KeyDescription(
        name="mcpServers",
        description="Model Context Protocol server configurations",
        example={},
        help_text="Advanced feature for connecting external tools and services. Usually empty for basic usage.",
        category="Advanced Features",
    ),
}


def get_key_description(key_path: str) -> Optional[KeyDescription]:
    """Get description for a configuration key by its path."""
    return CONFIG_KEY_DESCRIPTIONS.get(key_path)


def get_service_type_for_api_key(key_name: str) -> Optional[str]:
    """Determine the service type for an API key."""
    service_mapping = {
        "OPENAI_API_KEY": "openai",
        "ANTHROPIC_API_KEY": "anthropic",
        "OPENROUTER_API_KEY": "openrouter",
        "GEMINI_API_KEY": "google",
    }
    return service_mapping.get(key_name)


def get_categories() -> Dict[str, list[KeyDescription]]:
    """Get all configuration keys organized by category."""
    categories: Dict[str, list[KeyDescription]] = {}

    for desc in CONFIG_KEY_DESCRIPTIONS.values():
        if desc.category not in categories:
            categories[desc.category] = []
        categories[desc.category].append(desc)

    return categories


def get_configuration_glossary() -> str:
    """Generate a glossary of configuration terms for the help section."""
    glossary = """
[bold]Configuration Key Glossary[/bold]

[cyan]What are configuration keys?[/cyan]
Configuration keys are setting names (like 'default_model', 'max_retries') that control how TunaCode behaves.
Think of them like preferences in any app - they let you customize TunaCode to work the way you want.

[cyan]Key Categories:[/cyan]
• [yellow]AI Models[/yellow]: Which AI to use (GPT-4, Claude, etc.)
• [yellow]API Keys[/yellow]: Your credentials for AI services
• [yellow]Behavior Settings[/yellow]: How TunaCode acts (retries, iterations, etc.)
• [yellow]Tool Configuration[/yellow]: Which tools TunaCode can use
• [yellow]Performance Settings[/yellow]: Memory and speed optimizations
• [yellow]User Experience[/yellow]: Interface and tutorial preferences

[cyan]Common Examples:[/cyan]
• default_model → Which AI model to use by default
• max_retries → How many times to retry failed requests
• OPENAI_API_KEY → Your OpenAI account credentials
• tool_ignore → List of tools TunaCode shouldn't use
• context_window_size → How much conversation history to remember

[cyan]Default vs Custom:[/cyan]
• 📋 Default: TunaCode's built-in settings (work for most people)
• 🔧 Custom: Settings you've changed to fit your needs
"""
    return glossary.strip()
