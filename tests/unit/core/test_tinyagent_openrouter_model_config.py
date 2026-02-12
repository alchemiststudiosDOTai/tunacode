from __future__ import annotations

from pathlib import Path

import pytest

from tunacode.constants import ENV_OPENAI_BASE_URL

from tunacode.core.agents.agent_components import agent_config
from tunacode.core.compaction.controller import (
    CompactionController,
    UnsupportedCompactionProviderError,
)
from tunacode.core.session import StateManager

ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_CHUTES_API_KEY = "CHUTES_API_KEY"
OPENAI_COMPATIBLE_BASE_URL = "https://proxy.example/v1/chat/completions"
CHUTES_CHAT_COMPLETIONS_URL = "https://llm.chutes.ai/v1/chat/completions"


def _build_state_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StateManager:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    state_manager = StateManager()
    state_manager.session.project_id = "project-test"
    state_manager.session.created_at = "2026-02-11T00:00:00+00:00"
    state_manager.session.working_directory = "/tmp"
    state_manager.session.user_config["env"] = {}
    return state_manager


def test_build_tinyagent_model_propagates_openai_base_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    session = state_manager.session
    session.user_config["env"][ENV_OPENAI_BASE_URL] = OPENAI_COMPATIBLE_BASE_URL

    model = agent_config._build_tinyagent_model("openrouter:openai/gpt-4.1", session)

    assert model.provider == "openrouter"
    assert model.base_url == OPENAI_COMPATIBLE_BASE_URL


def test_build_tinyagent_model_allows_non_openrouter_provider_with_base_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    session = state_manager.session
    session.user_config["env"][ENV_OPENAI_BASE_URL] = OPENAI_COMPATIBLE_BASE_URL

    model = agent_config._build_tinyagent_model("chutes:deepseek-ai/DeepSeek-V3.1", session)

    assert model.provider == "chutes"
    assert model.id == "deepseek-ai/DeepSeek-V3.1"
    assert model.base_url == OPENAI_COMPATIBLE_BASE_URL


def test_build_tinyagent_model_uses_provider_registry_base_url_when_override_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    session = state_manager.session

    model = agent_config._build_tinyagent_model("chutes:deepseek-ai/DeepSeek-V3.1", session)

    assert model.provider == "chutes"
    assert model.base_url == CHUTES_CHAT_COMPLETIONS_URL


def test_build_tinyagent_model_raises_when_provider_has_no_api_and_override_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    session = state_manager.session

    with pytest.raises(ValueError, match="OPENAI_BASE_URL"):
        agent_config._build_tinyagent_model("azure:gpt-4.1", session)


def test_build_api_key_resolver_falls_back_to_openai_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    env = state_manager.session.user_config["env"]
    env[ENV_OPENAI_API_KEY] = "sk-openai"
    env[ENV_CHUTES_API_KEY] = "sk-chutes"

    resolver = agent_config._build_api_key_resolver(state_manager.session)

    assert resolver("chutes") == "sk-chutes"

    env[ENV_CHUTES_API_KEY] = ""
    assert resolver("chutes") == "sk-openai"


def test_compaction_controller_model_and_api_key_support_non_openrouter_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "chutes:deepseek-ai/DeepSeek-V3.1"

    env = state_manager.session.user_config["env"]
    env[ENV_OPENAI_BASE_URL] = OPENAI_COMPATIBLE_BASE_URL
    env[ENV_OPENAI_API_KEY] = "sk-openai"

    controller = CompactionController(state_manager=state_manager)

    model = controller._build_model()

    assert model.provider == "chutes"
    assert model.id == "deepseek-ai/DeepSeek-V3.1"
    assert model.base_url == OPENAI_COMPATIBLE_BASE_URL
    assert controller._resolve_api_key("chutes") == "sk-openai"

    env[ENV_CHUTES_API_KEY] = "sk-chutes"
    assert controller._resolve_api_key("chutes") == "sk-chutes"


def test_compaction_controller_uses_provider_registry_base_url_when_override_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "chutes:deepseek-ai/DeepSeek-V3.1"

    controller = CompactionController(state_manager=state_manager)

    model = controller._build_model()

    assert model.provider == "chutes"
    assert model.base_url == CHUTES_CHAT_COMPLETIONS_URL


def test_compaction_controller_raises_when_provider_has_no_api_and_override_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "azure:gpt-4.1"

    controller = CompactionController(state_manager=state_manager)

    with pytest.raises(UnsupportedCompactionProviderError, match="azure"):
        controller._build_model()
