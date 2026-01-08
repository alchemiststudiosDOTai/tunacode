"""Prompt templates for composing system prompts from sections."""

# Main agent template - default composition order
# SEARCH_PATTERN is placed early to ensure the agent sees the search funnel first
MAIN_TEMPLATE = """{{AGENT_ROLE}}

====

{{SEARCH_PATTERN}}

====

{{CRITICAL_RULES}}

====

{{TOOL_USE}}

====

{{COMPLETION}}

====

{{PARALLEL_EXEC}}

====

{{OUTPUT_STYLE}}

====

{{EXAMPLES}}

====

{{ADVANCED_PATTERNS}}

====

{{SYSTEM_INFO}}

====

{{USER_INSTRUCTIONS}}"""

# Research agent template - simpler structure focused on exploration
RESEARCH_TEMPLATE = """{{AGENT_ROLE}}

====

{{TOOL_USE}}

====

{{CONSTRAINTS}}

====

{{OUTPUT_FORMAT}}"""

# Minimal template for local/small models
LOCAL_TEMPLATE = """{{AGENT_ROLE}}

====

{{TOOL_USE}}

====

{{USER_INSTRUCTIONS}}"""

# Model-specific template overrides
# Key: model name prefix (e.g., "gpt-5", "claude-opus")
# Value: custom template string
TEMPLATE_OVERRIDES: dict[str, str] = {
    # Example:
    # "gpt-5": GPT5_TEMPLATE,
    # "claude-opus": OPUS_TEMPLATE,
}
