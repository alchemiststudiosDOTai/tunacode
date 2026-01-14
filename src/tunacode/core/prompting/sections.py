"""System prompt section definitions."""

from enum import Enum


class SystemPromptSection(str, Enum):
    """Named sections for composing system prompts.

    Each section corresponds to a file in the prompts/sections/ directory.
    Section files can be .xml, .md, or .txt format.
    """

    # Core agent identity and behavior
    AGENT_ROLE = "AGENT_ROLE"

    # Mandatory behavior rules and constraints
    CRITICAL_RULES = "CRITICAL_RULES"

    # Tool descriptions and access rules
    TOOL_USE = "TOOL_USE"

    # GLOB->GREP->READ search pattern guidance
    SEARCH_PATTERN = "SEARCH_PATTERN"

    # Task completion signaling (submit tool)
    COMPLETION = "COMPLETION"

    # Parallel execution rules for read-only tools
    PARALLEL_EXEC = "PARALLEL_EXEC"

    # Output formatting and style guidelines
    OUTPUT_STYLE = "OUTPUT_STYLE"

    # Few-shot examples and workflow demonstrations
    EXAMPLES = "EXAMPLES"

    # Advanced usage patterns
    ADVANCED_PATTERNS = "ADVANCED_PATTERNS"

    # Dynamic system info (CWD, OS, DATE placeholders)
    SYSTEM_INFO = "SYSTEM_INFO"

    # User-provided context and instructions
    USER_INSTRUCTIONS = "USER_INSTRUCTIONS"

    # Research-specific: structured output format
    OUTPUT_FORMAT = "OUTPUT_FORMAT"

    # Research-specific: file limits and constraints
    CONSTRAINTS = "CONSTRAINTS"
