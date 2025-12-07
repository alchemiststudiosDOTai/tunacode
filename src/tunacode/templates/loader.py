"""Template metadata for TunaCode templates."""

from dataclasses import dataclass, field


@dataclass
class Template:
    """Represents a template with metadata and allowed tools."""

    name: str
    description: str
    prompt: str
    allowed_tools: list[str]
    parameters: dict[str, str] = field(default_factory=dict)
    shortcut: str | None = None
