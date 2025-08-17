"""
TunaCode CLI exception hierarchy.

This module defines all custom exceptions used throughout the TunaCode CLI.
All exceptions inherit from TunaCodeError for easy catching of any TunaCode-specific error.
"""

from tunacode.types import ErrorMessage, FilePath, OriginalError, ToolName


class TunaCodeError(Exception):
    """Base exception for all TunaCode errors."""

    pass


# Configuration and Setup Exceptions
class ConfigurationError(TunaCodeError):
    """Raised when there's a configuration issue."""

    def __init__(
        self,
        message: str,
        suggested_actions: list = None,
        help_links: list = None,
        quick_fix: str = None
    ):
        self.suggested_actions = suggested_actions or []
        self.help_links = help_links or []
        self.quick_fix = quick_fix

        # Enhance message with actionable guidance
        enhanced_message = message

        if quick_fix:
            enhanced_message += f"\n\n💡 Quick fix: {quick_fix}"

        if self.suggested_actions:
            enhanced_message += "\n\n🔧 Suggested actions:"
            for i, action in enumerate(self.suggested_actions, 1):
                enhanced_message += f"\n  {i}. {action}"

        if self.help_links:
            enhanced_message += "\n\n📚 More help:"
            for link in self.help_links:
                enhanced_message += f"\n  • {link}"

        super().__init__(enhanced_message)


class OnboardingError(ConfigurationError):
    """Raised when there are issues during the onboarding process."""

    def __init__(self, step: str, message: str, recovery_action: str = None):
        self.step = step
        self.recovery_action = recovery_action

        suggested_actions = [
            "Try running the wizard again: tunacode --wizard",
            "Use quick CLI setup: tunacode --model 'provider:model' --key 'your-key'",
            "Get help: tunacode --help"
        ]

        if recovery_action:
            suggested_actions.insert(0, recovery_action)

        help_links = [
            "Setup guide: https://docs.tunacode.ai/setup",
            "Troubleshooting: https://docs.tunacode.ai/troubleshooting"
        ]

        super().__init__(
            f"Onboarding failed at step '{step}': {message}",
            suggested_actions=suggested_actions,
            help_links=help_links,
            quick_fix="tunacode --wizard"
        )


# User Interaction Exceptions
class UserAbortError(TunaCodeError):
    """Raised when user aborts an operation."""

    pass


class ValidationError(TunaCodeError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: str = None,
        expected_format: str = None,
        example: str = None
    ):
        self.field = field
        self.expected_format = expected_format
        self.example = example

        enhanced_message = message

        if expected_format:
            enhanced_message += f"\n\n📋 Expected format: {expected_format}"

        if example:
            enhanced_message += f"\n💡 Example: {example}"

        if field:
            enhanced_message += f"\n🎯 Field: {field}"

        super().__init__(enhanced_message)


class ModelConfigurationError(ConfigurationError):
    """Raised when there are issues with model configuration."""

    def __init__(self, model: str = None, provider: str = None, issue: str = None):
        self.model = model
        self.provider = provider
        self.issue = issue

        if model and ":" not in model:
            message = f"Invalid model format: '{model}'. Models must include provider prefix."
            suggested_actions = [
                "Use format 'provider:model', e.g., 'openai:gpt-4'",
                "Run setup wizard: tunacode --wizard",
                "See available models: /model list"
            ]
            quick_fix = "tunacode --model 'openai:gpt-4' --key 'your-key'"
        elif issue:
            message = f"Model configuration issue: {issue}"
            suggested_actions = [
                "Check your API key is valid",
                "Verify the model name is correct",
                "Try a different model: /model",
                "Run setup wizard: tunacode --wizard"
            ]
            quick_fix = "tunacode --wizard"
        else:
            message = f"Model configuration error for {model or 'unknown model'}"
            suggested_actions = [
                "Run setup wizard: tunacode --wizard",
                "Check model format: provider:model-name",
                "Verify API key: check your provider's dashboard"
            ]
            quick_fix = "tunacode --wizard"

        help_links = [
            "Model setup guide: https://docs.tunacode.ai/models",
            "Supported providers: https://docs.tunacode.ai/providers"
        ]

        super().__init__(
            message,
            suggested_actions=suggested_actions,
            help_links=help_links,
            quick_fix=quick_fix
        )


class FirstTimeSetupError(ConfigurationError):
    """Raised when first-time setup encounters issues."""

    def __init__(self, error_type: str, details: str = None):
        self.error_type = error_type

        if error_type == "no_api_key":
            message = "No API key provided during setup"
            suggested_actions = [
                "Get an API key from your preferred provider",
                "Run the setup wizard: tunacode --wizard",
                "Use CLI setup: tunacode --model 'provider:model' --key 'your-key'"
            ]
            help_links = [
                "OpenAI keys: https://platform.openai.com/account/api-keys",
                "Anthropic keys: https://console.anthropic.com/",
                "Setup guide: https://docs.tunacode.ai/setup"
            ]
            quick_fix = "tunacode --wizard"

        elif error_type == "invalid_model":
            message = f"Invalid model configuration: {details}"
            suggested_actions = [
                "Check the model name format: provider:model-name",
                "Verify the model exists with your provider",
                "Run setup wizard for guidance: tunacode --wizard"
            ]
            help_links = [
                "Supported models: https://docs.tunacode.ai/models"
            ]
            quick_fix = "tunacode --wizard"

        else:
            message = f"Setup error: {error_type}"
            if details:
                message += f" - {details}"
            suggested_actions = [
                "Try the setup wizard: tunacode --wizard",
                "Check the troubleshooting guide",
                "Contact support if the issue persists"
            ]
            help_links = [
                "Troubleshooting: https://docs.tunacode.ai/troubleshooting"
            ]
            quick_fix = "tunacode --wizard"

        super().__init__(
            message,
            suggested_actions=suggested_actions,
            help_links=help_links,
            quick_fix=quick_fix
        )


# Tool and Agent Exceptions
class ToolExecutionError(TunaCodeError):
    """Raised when a tool fails to execute."""

    def __init__(
        self, tool_name: ToolName, message: ErrorMessage, original_error: OriginalError = None
    ):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class AgentError(TunaCodeError):
    """Raised when agent operations fail."""

    pass


# State Management Exceptions
class StateError(TunaCodeError):
    """Raised when there's an issue with application state."""

    pass


# External Service Exceptions
class ServiceError(TunaCodeError):
    """Base exception for external service failures."""

    pass


class MCPError(ServiceError):
    """Raised when MCP server operations fail."""

    def __init__(
        self, server_name: str, message: ErrorMessage, original_error: OriginalError = None
    ):
        self.server_name = server_name
        self.original_error = original_error
        super().__init__(f"MCP server '{server_name}' error: {message}")


class GitOperationError(ServiceError):
    """Raised when Git operations fail."""

    def __init__(self, operation: str, message: ErrorMessage, original_error: OriginalError = None):
        self.operation = operation
        self.original_error = original_error
        super().__init__(f"Git {operation} failed: {message}")


# File System Exceptions
class FileOperationError(TunaCodeError):
    """Raised when file system operations fail."""

    def __init__(
        self,
        operation: str,
        path: FilePath,
        message: ErrorMessage,
        original_error: OriginalError = None,
    ):
        self.operation = operation
        self.path = path
        self.original_error = original_error
        super().__init__(f"File {operation} failed for '{path}': {message}")


class TooBroadPatternError(ToolExecutionError):
    """Raised when a search pattern is too broad and times out."""

    def __init__(self, pattern: str, timeout_seconds: float):
        self.pattern = pattern
        self.timeout_seconds = timeout_seconds
        super().__init__(
            "grep",
            f"Pattern '{pattern}' is too broad - no matches found within {timeout_seconds}s. "
            "Please use a more specific pattern.",
        )


class ToolBatchingJSONError(TunaCodeError):
    """Raised when JSON parsing fails during tool batching after all retries are exhausted."""

    def __init__(
        self,
        json_content: str,
        retry_count: int,
        original_error: OriginalError = None,
    ):
        self.json_content = json_content
        self.retry_count = retry_count
        self.original_error = original_error

        # Truncate JSON content for display if too long
        display_content = json_content[:100] + "..." if len(json_content) > 100 else json_content

        super().__init__(
            f"The model is having issues with tool batching. "
            f"JSON parsing failed after {retry_count} retries. "
            f"Invalid JSON: {display_content}"
        )
