from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class SkillSource(StrEnum):
    """Filesystem origin for a discovered skill."""

    LOCAL = "local"
    GLOBAL = "global"


@dataclass(frozen=True, slots=True)
class SkillSummary:
    """Metadata loaded at startup without reading the full skill body."""

    name: str
    description: str
    source: SkillSource
    skill_dir: Path
    skill_path: Path


@dataclass(frozen=True, slots=True)
class LoadedSkill:
    """Fully loaded skill content and validated relative references."""

    name: str
    description: str
    source: SkillSource
    skill_dir: Path
    skill_path: Path
    content: str
    referenced_paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class SelectedSkill:
    """Attached skill state for prompt rendering within a session."""

    name: str
    source: SkillSource
    skill_dir: Path
    skill_path: Path
    referenced_paths: tuple[Path, ...]
    related_paths: tuple[Path, ...]
    content: str
    attachment_index: int


@dataclass(frozen=True, slots=True)
class ResolvedSelectedSkillSummary:
    """Display-friendly selected-skill projection that preserves missing entries."""

    requested_name: str
    summary: SkillSummary | None
