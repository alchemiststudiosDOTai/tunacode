"""Prompt and repo context loading helpers for agent configuration."""

from __future__ import annotations

from pathlib import Path

from tunacode.constants import AGENTS_MD

from tunacode.infrastructure.cache.caches import tunacode_context as context_cache

from tunacode.core.logging.manager import get_logger


def load_system_prompt(base_path: Path, model: str | None = None) -> str:
    _ = model
    prompt_file = base_path / "prompts" / "system_prompt.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Required prompt file not found: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def load_tunacode_context() -> str:
    logger = get_logger()
    try:
        tunacode_path = Path.cwd() / AGENTS_MD
        return context_cache.get_context(tunacode_path)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Unexpected error loading guide file: {exc}")
        raise
