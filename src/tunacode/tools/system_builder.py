"""System prompt builder that integrates tool documentation.

This module builds system prompts dynamically by combining base content
with generated tool documentation from the registry.
"""

from pathlib import Path

from .prompt_generator import PromptGenerator


class SystemPromptBuilder:
    """Builds system prompts with dynamic tool documentation."""

    @staticmethod
    def load_base_prompt() -> str:
        """Load the base system prompt without tool documentation.

        Returns:
            Base system prompt content
        """
        # Try to load from the standard location
        base_path = Path(__file__).parent.parent / "prompts" / "system.md"

        if base_path.exists():
            try:
                with open(base_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                return content
            except Exception:
                pass

        # Fallback to minimal prompt
        return """You are a helpful AI assistant with access to various tools.
Use the tools available to help complete tasks efficiently."""

    @staticmethod
    def build_system_prompt(include_tools: bool = True) -> str:
        """Build complete system prompt with optional tool documentation.

        Args:
            include_tools: Whether to include tool documentation

        Returns:
            Complete system prompt
        """
        base_prompt = SystemPromptBuilder.load_base_prompt()

        if not include_tools:
            return base_prompt

        # Check if base prompt has a tools placeholder
        if "{{TOOLS}}" in base_prompt:
            tool_docs = PromptGenerator.generate_all_tools()
            return base_prompt.replace("{{TOOLS}}", tool_docs)
        else:
            # Append tools section if no placeholder
            tool_docs = PromptGenerator.generate_all_tools()
            return f"{base_prompt}\n\n{tool_docs}"

    @staticmethod
    def build_for_model(model: str, include_tools: bool = True) -> str:
        """Build system prompt optimized for a specific model.

        Args:
            model: Model identifier (e.g., 'claude-3', 'gpt-4')
            include_tools: Whether to include tool documentation

        Returns:
            Model-optimized system prompt
        """
        prompt = SystemPromptBuilder.build_system_prompt(include_tools)

        # Model-specific adjustments could be added here
        # For now, return the standard prompt
        return prompt
