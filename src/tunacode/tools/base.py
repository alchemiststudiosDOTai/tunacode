"""Base tool class for all TunaCode tools.

This module provides a base class that implements common patterns
for all tools including error handling, UI logging, and ModelRetry support.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic_ai.exceptions import ModelRetry

from tunacode.core.logging.logger import get_logger
from tunacode.exceptions import FileOperationError, ToolExecutionError
from tunacode.types import FilePath, ToolName, ToolResult, UILogger


class BaseTool(ABC):
    """Base class for all TunaCode tools providing common functionality."""

    def __init__(self, ui_logger: UILogger | None = None):
        """Initialize the base tool.

        Args:
            ui_logger: UI logger instance for displaying messages
        """
        self.ui = ui_logger
        self.logger = get_logger(self.__class__.__name__)
        self._prompt_cache: Optional[str] = None
        self._context: Dict[str, Any] = {}
        self._resources: List[Any] = []  # Track resources for cleanup

    async def execute(self, *args, **kwargs) -> ToolResult:
        """Execute the tool with error handling and logging.

        This method wraps the tool-specific logic with:
        - UI logging of the operation
        - Exception handling (except ModelRetry and ToolExecutionError)
        - Consistent error message formatting
        - Resource cleanup on any exception

        Returns:
            str: Success message

        Raises:
            ModelRetry: Re-raised to guide the LLM
            ToolExecutionError: Raised for all other errors with structured information
        """
        try:
            msg = f"{self.tool_name}({self._format_args(*args, **kwargs)})"
            if self.ui:
                await self.ui.info(msg)
            self.logger.info(msg)
            result = await self._execute(*args, **kwargs)
            return result
        except ModelRetry as e:
            # Log as warning and re-raise for pydantic-ai
            if self.ui:
                await self.ui.warning(str(e))
            self.logger.warning(f"ModelRetry: {e}")
            raise
        except ToolExecutionError:
            # Already properly formatted, just re-raise
            raise
        except Exception as e:
            # Handle any other exceptions
            await self._handle_error(e, *args, **kwargs)
        finally:
            # Ensure resource cleanup even on success or failure
            await self.cleanup()

    @property
    @abstractmethod
    def tool_name(self) -> ToolName:
        """Return the display name for this tool."""
        pass

    @abstractmethod
    async def _execute(self, *args, **kwargs) -> ToolResult:
        """Implement tool-specific logic here.

        This method should contain the core functionality of the tool.

        Returns:
            str: Success message describing what was done

        Raises:
            ModelRetry: When the LLM needs guidance
            Exception: Any other errors will be caught and handled
        """
        pass

    async def cleanup(self) -> None:
        """Clean up any resources created during tool execution.

        This method is called automatically in a finally block after tool execution.
        Subclasses should override this to implement tool-specific cleanup logic.

        The base implementation handles cleanup of any resources registered via
        register_resource(), attempting to call close() or cleanup() methods.
        """
        for resource in self._resources:
            try:
                if hasattr(resource, "close"):
                    if asyncio.iscoroutinefunction(resource.close):
                        await resource.close()
                    else:
                        resource.close()
                elif hasattr(resource, "cleanup"):
                    if asyncio.iscoroutinefunction(resource.cleanup):
                        await resource.cleanup()
                    else:
                        resource.cleanup()
            except Exception as e:
                self.logger.warning(f"Failed to clean up resource {resource}: {e}")

        # Clear the resource list
        self._resources.clear()

    def register_resource(self, resource: Any) -> None:
        """Register a resource for automatic cleanup.

        Resources registered here will be automatically cleaned up in the finally
        block of execute(), regardless of success or failure.

        Args:
            resource: Any object with a close() or cleanup() method
        """
        self._resources.append(resource)

    async def __aenter__(self):
        """Enter async context manager."""
        return self

    async def __aexit__(self, exc_type, _, __):
        """Exit async context manager and cleanup resources."""
        await self.cleanup()
        return False

    async def _handle_error(self, error: Exception, *args, **kwargs) -> ToolResult:
        """Handle errors by logging and raising proper exceptions.

        Args:
            error: The exception that was raised
            *args, **kwargs: Original arguments for context

        Raises:
            ToolExecutionError: Always raised with structured error information
        """
        # Format error message for display
        err_msg = f"Error {self._get_error_context(*args, **kwargs)}: {error}"
        if self.ui:
            await self.ui.error(err_msg)
        self.logger.error(err_msg)

        # Raise proper exception instead of returning string
        raise ToolExecutionError(tool_name=self.tool_name, message=str(error), original_error=error)

    def _format_args(self, *args, **kwargs) -> str:
        """Format arguments for display in UI logging.

        Override this method to customize how arguments are displayed.

        Returns:
            str: Formatted argument string
        """
        # Collect all arguments
        all_args = []

        # Add positional arguments
        for arg in args:
            if isinstance(arg, str) and len(arg) > 50:
                # Truncate long strings
                all_args.append(f"'{arg[:47]}...'")
            else:
                all_args.append(repr(arg))

        # Add keyword arguments
        for key, value in kwargs.items():
            if isinstance(value, str) and len(value) > 50:
                all_args.append(f"{key}='{value[:47]}...'")
            else:
                all_args.append(f"{key}={repr(value)}")

        return ", ".join(all_args)

    def _get_error_context(self, *args, **kwargs) -> str:
        """Get context string for error messages.

        Override this method to provide tool-specific error context.

        Returns:
            str: Context for the error message
        """
        return f"in {self.tool_name}"

    def prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate the prompt for this tool.

        Args:
            context: Optional context including model, permissions, environment

        Returns:
            str: The generated prompt for this tool
        """
        # Update context if provided
        if context:
            self._context.update(context)

        # Check cache if context hasn't changed
        cache_key = str(sorted(self._context.items()))
        if self._prompt_cache and cache_key == getattr(self, "_cache_key", None):
            return self._prompt_cache

        # Generate new prompt
        prompt = self._generate_prompt()

        # Cache the result
        self._prompt_cache = prompt
        self._cache_key = cache_key

        return prompt

    def _generate_prompt(self) -> str:
        """Generate the actual prompt based on current context.

        Override this method in subclasses to provide tool-specific prompts.

        Returns:
            str: The generated prompt
        """
        # Default prompt generation
        base_prompt = self._get_base_prompt()

        # Apply model-specific adjustments
        if "model" in self._context:
            base_prompt = self._adjust_for_model(base_prompt, self._context["model"])

        # Apply permission-specific adjustments
        if "permissions" in self._context:
            base_prompt = self._adjust_for_permissions(base_prompt, self._context["permissions"])

        return base_prompt

    def _get_base_prompt(self) -> str:
        """Get the base prompt for this tool.

        Override this in subclasses to provide tool-specific base prompts.

        Returns:
            str: The base prompt template
        """
        return f"Execute the {self.tool_name} tool to perform its designated operation."

    def _adjust_for_model(self, prompt: str, model: str) -> str:
        """Adjust prompt based on the model being used.

        Args:
            prompt: The base prompt
            model: The model identifier

        Returns:
            str: Adjusted prompt
        """
        # Default implementation - override in subclasses for specific adjustments
        return prompt

    def _adjust_for_permissions(self, prompt: str, permissions: Dict[str, Any]) -> str:
        """Adjust prompt based on permissions.

        Args:
            prompt: The base prompt
            permissions: Permission settings

        Returns:
            str: Adjusted prompt
        """
        # Default implementation - override in subclasses for specific adjustments
        return prompt

    def get_tool_schema(self) -> Dict[str, Any]:
        """Generate the tool schema for API integration.

        Returns:
            Dict containing the tool schema in OpenAI function format
        """
        return {
            "name": self.tool_name,
            "description": self.prompt(),
            "parameters": self._get_parameters_schema(),
        }

    @abstractmethod
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get the parameters schema for this tool.

        Must be implemented by subclasses.

        Returns:
            Dict containing the JSON schema for tool parameters
        """
        pass


class FileBasedTool(BaseTool):
    """Base class for tools that work with files.

    Provides common file-related functionality like:
    - Path validation
    - File existence checking
    - Directory creation
    - Encoding handling
    - Enhanced error handling for file operations
    """

    def _format_args(self, filepath: FilePath, *args, **kwargs) -> str:
        """Format arguments with filepath as first argument."""
        # Always show the filepath first
        all_args = [repr(filepath)]

        # Add remaining positional arguments
        for arg in args:
            if isinstance(arg, str) and len(arg) > 50:
                all_args.append(f"'{arg[:47]}...'")
            else:
                all_args.append(repr(arg))

        # Add keyword arguments
        for key, value in kwargs.items():
            if isinstance(value, str) and len(value) > 50:
                all_args.append(f"{key}='{value[:47]}...'")
            else:
                all_args.append(f"{key}={repr(value)}")

        return ", ".join(all_args)

    def _get_error_context(self, filepath: FilePath = None, *args, **kwargs) -> str:
        """Get error context including file path."""
        if filepath:
            return f"handling file '{filepath}'"
        return super()._get_error_context(*args, **kwargs)

    async def _handle_error(self, error: Exception, *args, **kwargs) -> ToolResult:
        """Handle file-specific errors.

        Overrides base class to create FileOperationError for file-related issues.

        Raises:
            ToolExecutionError: Always raised with structured error information
        """
        filepath = args[0] if args else kwargs.get("filepath", "unknown")

        # Check if this is a file-related error
        if isinstance(error, (IOError, OSError, PermissionError, FileNotFoundError)):
            # Determine the operation based on the tool name
            operation = self.tool_name.replace("_", " ")

            # Create a FileOperationError
            file_error = FileOperationError(
                operation=operation, path=str(filepath), message=str(error), original_error=error
            )

            # Format error message for display
            err_msg = str(file_error)
            if self.ui:
                await self.ui.error(err_msg)

            # Raise ToolExecutionError with the file error
            raise ToolExecutionError(
                tool_name=self.tool_name, message=str(file_error), original_error=file_error
            )

        # For non-file errors, use the base class handling
        await super()._handle_error(error, *args, **kwargs)
