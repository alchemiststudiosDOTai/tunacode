"""Tool Schema Assembler for API Integration.

This module handles the assembly of tool schemas for API calls,
converting tool prompts and parameters into OpenAI-compatible function schemas.
"""

from typing import Any, Dict, List, Optional, Type

from tunacode.tools.base import BaseTool


class ToolSchemaAssembler:
    """Assembles tool schemas for API integration."""

    def __init__(self):
        """Initialize the schema assembler."""
        self._context: Dict[str, Any] = {}
        self._tool_instances: Dict[str, BaseTool] = {}

    def set_context(self, context: Dict[str, Any]) -> None:
        """Set the context for all tools.

        Args:
            context: Context including model, permissions, environment, etc.
        """
        self._context = context
        # Update context for all registered tools
        for tool in self._tool_instances.values():
            tool._context.update(context)

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Args:
            tool: The tool instance to register
        """
        self._tool_instances[tool.tool_name] = tool
        # Apply current context to the new tool
        if self._context:
            tool._context.update(self._context)

    def register_tool_class(self, tool_class: Type[BaseTool], *args, **kwargs) -> None:
        """Register a tool by instantiating its class.

        Args:
            tool_class: The tool class to instantiate
            *args, **kwargs: Arguments for tool instantiation
        """
        tool = tool_class(*args, **kwargs)
        self.register_tool(tool)

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get the schema for a specific tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool schema in OpenAI function format, or None if not found
        """
        # Check feature flags
        from .feature_flags import ToolFeatureFlags

        if ToolFeatureFlags.use_unified_registry():
            # Try registry first
            from .registry import ToolRegistry

            definition = ToolRegistry.get(tool_name)
            if definition:
                return {
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": definition.parameters,
                }

        # Fall back to existing implementation
        tool = self._tool_instances.get(tool_name)
        if not tool:
            return None

        return tool.get_tool_schema()

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get schemas for all registered tools.

        Returns:
            List of tool schemas in OpenAI function format
        """
        schemas = []
        for tool in self._tool_instances.values():
            schema = tool.get_tool_schema()
            if schema:
                schemas.append(schema)
        return schemas

    def get_schemas_for_model(self, model: str) -> List[Dict[str, Any]]:
        """Get schemas optimized for a specific model.

        Args:
            model: The model identifier (e.g., 'claude-3', 'gpt-4')

        Returns:
            List of tool schemas optimized for the model
        """
        # Update context with model
        self.set_context({"model": model, **self._context})

        # Get all schemas with model-specific prompts
        return self.get_all_schemas()

    def get_schemas_with_permissions(self, permissions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get schemas filtered by permissions.

        Args:
            permissions: Permission settings

        Returns:
            List of tool schemas filtered by permissions
        """
        # Update context with permissions
        self.set_context({"permissions": permissions, **self._context})

        # Filter tools based on permissions
        schemas = []
        for tool_name, tool in self._tool_instances.items():
            # Check if tool is allowed based on permissions
            if self._is_tool_allowed(tool_name, permissions):
                schema = tool.get_tool_schema()
                if schema:
                    schemas.append(schema)

        return schemas

    def _is_tool_allowed(self, tool_name: str, permissions: Dict[str, Any]) -> bool:
        """Check if a tool is allowed based on permissions.

        Args:
            tool_name: Name of the tool
            permissions: Permission settings

        Returns:
            True if the tool is allowed
        """
        # Default implementation - can be extended
        if permissions.get("restricted", False):
            # In restricted mode, only allow safe tools
            safe_tools = ["read_file", "list_dir", "grep", "glob"]
            return tool_name in safe_tools

        # Check for explicit tool permissions
        allowed_tools = permissions.get("allowed_tools")
        if allowed_tools:
            return tool_name in allowed_tools

        blocked_tools = permissions.get("blocked_tools", [])
        return tool_name not in blocked_tools

    def refresh_prompts(self) -> None:
        """Refresh prompts for all tools based on current context."""
        for tool in self._tool_instances.values():
            # Clear prompt cache to force regeneration
            tool._prompt_cache = None

    def update_environment(self, env_vars: Dict[str, Any]) -> None:
        """Update environment variables in context.

        Args:
            env_vars: Environment variables to update
        """
        current_env = self._context.get("environment", {})
        current_env.update(env_vars)
        self.set_context({"environment": current_env, **self._context})

    def get_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        """Get a tool instance by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self._tool_instances.get(tool_name)
