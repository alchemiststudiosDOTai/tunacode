"""Shared session/config helpers for agent construction."""

from __future__ import annotations

# ruff: noqa: I001

from dataclasses import dataclass

from tunacode.skills.models import SelectedSkill
from tunacode.core.types.state import SessionStateProtocol


@dataclass(frozen=True, slots=True)
class AgentSettings:
    request_delay: float
    global_request_timeout: float | None
    max_retries: int
    tool_strict_validation: bool
    max_iterations: int
    max_command_output: int
    max_tokens: int | None


@dataclass(frozen=True, slots=True)
class SessionConfig:
    settings: AgentSettings
    env: dict[str, str]


@dataclass(frozen=True, slots=True)
class SkillsPromptState:
    available_block: str
    selected_block: str
    fingerprint: str
    selected_skills: list[SelectedSkill]


def _normalize_session_config(session: SessionStateProtocol) -> SessionConfig:
    user_config = session.user_config
    raw_settings = user_config["settings"]
    request_delay = raw_settings["request_delay"]
    if request_delay < 0.0 or request_delay > 60.0:
        raise ValueError(f"request_delay must be between 0.0 and 60.0 seconds, got {request_delay}")

    timeout = raw_settings["global_request_timeout"]
    if timeout < 0.0:
        raise ValueError(f"global_request_timeout must be >= 0.0 seconds, got {timeout}")

    env_config = {key: value.strip() for key, value in user_config["env"].items() if value.strip()}

    settings = AgentSettings(
        request_delay=request_delay,
        global_request_timeout=None if timeout == 0.0 else timeout,
        max_retries=raw_settings["max_retries"],
        tool_strict_validation=raw_settings["tool_strict_validation"],
        max_iterations=raw_settings["max_iterations"],
        max_command_output=raw_settings["max_command_output"],
        max_tokens=raw_settings["max_tokens"],
    )
    if settings.max_retries < 1:
        raise ValueError(f"max_retries must be >= 1, got {settings.max_retries}")
    if settings.max_iterations < 1:
        raise ValueError(f"max_iterations must be >= 1, got {settings.max_iterations}")
    return SessionConfig(settings=settings, env=env_config)


def _coerce_session_config(config: SessionConfig | SessionStateProtocol) -> SessionConfig:
    if isinstance(config, SessionConfig):
        return config
    return _normalize_session_config(config)


def _coerce_request_delay(session: SessionStateProtocol) -> float:
    return _normalize_session_config(session).settings.request_delay


def _coerce_global_request_timeout(session: SessionStateProtocol) -> float | None:
    return _normalize_session_config(session).settings.global_request_timeout


def _coerce_max_iterations(session: SessionStateProtocol) -> int:
    return _normalize_session_config(session).settings.max_iterations


def _compute_agent_version(
    settings: AgentSettings,
    *,
    max_tokens: int | None,
    skills_prompt_fingerprint: str,
) -> int:
    return hash(
        (
            settings.max_retries,
            settings.tool_strict_validation,
            settings.request_delay,
            settings.global_request_timeout,
            max_tokens,
            3,
            skills_prompt_fingerprint,
        )
    )
