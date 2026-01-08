"""Prompting engine for dynamic placeholder resolution and section composition."""

from tunacode.core.prompting.loader import SectionLoader
from tunacode.core.prompting.prompting_engine import (
    PromptingEngine,
    compose_prompt,
    get_prompting_engine,
    resolve_prompt,
)
from tunacode.core.prompting.sections import SystemPromptSection
from tunacode.core.prompting.templates import (
    LOCAL_TEMPLATE,
    MAIN_TEMPLATE,
    RESEARCH_TEMPLATE,
    TEMPLATE_OVERRIDES,
)

__all__ = [
    "PromptingEngine",
    "get_prompting_engine",
    "resolve_prompt",
    "compose_prompt",
    "SystemPromptSection",
    "LOCAL_TEMPLATE",
    "MAIN_TEMPLATE",
    "RESEARCH_TEMPLATE",
    "TEMPLATE_OVERRIDES",
    "SectionLoader",
]
