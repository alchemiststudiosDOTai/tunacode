from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tunacode.constants import ENV_OPENAI_BASE_URL

from tunacode.core.agents.agent_components import agent_config
from tunacode.core.compaction import controller as compaction_controller
from tunacode.core.compaction.controller import (
    CompactionController,
    UnsupportedCompactionProviderError,
)
from tunacode.core.session import StateManager

ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_CHUTES_API_KEY = "CHUTES_API_KEY"
OPENAI_COMPATIBLE_BASE_URL = "https://proxy.example/v1/chat/completions"
CHUTES_CHAT_COMPLETIONS_URL = "https://llm.chutes.ai/v1/chat/completions"
MINIMAX_CHAT_COMPLETIONS_URL = "https://api.minimax.io/v1/chat/completions"
MINIMAX_CN_CHAT_COMPLETIONS_URL = "https://api.minimaxi.com/v1/chat/completions"
MINIMAX_ALCHEMY_API = "minimax-completions"
ENV_MINIMAX_CN_API_KEY = "MINIMAX_CN_API_KEY"


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


def test_build_tinyagent_model_uses_minimax_alchemy_contract_from_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    session = state_manager.session

    model = agent_config._build_tinyagent_model("minimax:MiniMax-M2.1", session)

    assert model.provider == "minimax"
    assert model.id == "MiniMax-M2.1"
    assert model.api == MINIMAX_ALCHEMY_API
    assert model.base_url == MINIMAX_CHAT_COMPLETIONS_URL


def test_build_tinyagent_model_uses_minimax_coding_plan_alchemy_contract_from_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    session = state_manager.session

    model = agent_config._build_tinyagent_model("minimax-coding-plan:MiniMax-M2.1", session)

    assert model.provider == "minimax-coding-plan"
    assert model.id == "MiniMax-M2.1"
    assert model.api == MINIMAX_ALCHEMY_API
    assert model.base_url == MINIMAX_CHAT_COMPLETIONS_URL


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


def test_build_api_key_resolver_prefers_minimax_cn_provider_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    env = state_manager.session.user_config["env"]
    env[ENV_OPENAI_API_KEY] = "sk-openai"
    env[ENV_MINIMAX_CN_API_KEY] = "sk-minimax-cn"

    resolver = agent_config._build_api_key_resolver(state_manager.session)

    assert resolver("minimax-cn") == "sk-minimax-cn"

    env[ENV_MINIMAX_CN_API_KEY] = ""
    assert resolver("minimax-cn") == "sk-openai"


@pytest.mark.asyncio
async def test_build_stream_fn_uses_alchemy_stream_and_overrides_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_options: dict[str, Any] = {}

    async def _fake_stream(model: Any, context: Any, options: dict[str, Any]) -> object:
        _ = model
        _ = context
        captured_options.update(options)
        return {"ok": True}

    monkeypatch.setattr(agent_config, "stream_alchemy_openai_completions", _fake_stream)

    stream_fn = agent_config._build_stream_fn(request_delay=0.0, max_tokens=128)
    original_options: dict[str, Any] = {"api_key": "sk-test", "max_tokens": None}

    result = await stream_fn(object(), object(), original_options)

    assert result == {"ok": True}
    assert captured_options["api_key"] == "sk-test"
    assert captured_options["max_tokens"] == 128
    assert original_options["max_tokens"] is None


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


def test_compaction_controller_build_model_threads_minimax_coding_plan_alchemy_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "minimax-coding-plan:MiniMax-M2.1"

    controller = CompactionController(state_manager=state_manager)

    model = controller._build_model()

    assert model.provider == "minimax-coding-plan"
    assert model.id == "MiniMax-M2.1"
    assert model.api == MINIMAX_ALCHEMY_API
    assert model.base_url == MINIMAX_CHAT_COMPLETIONS_URL


def test_compaction_controller_uses_minimax_cn_provider_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "minimax-cn:MiniMax-M2.1"
    env = state_manager.session.user_config["env"]
    env[ENV_OPENAI_API_KEY] = "sk-openai"
    env[ENV_MINIMAX_CN_API_KEY] = "sk-minimax-cn"

    controller = CompactionController(state_manager=state_manager)

    model = controller._build_model()

    assert model.provider == "minimax-cn"
    assert model.api == MINIMAX_ALCHEMY_API
    assert model.base_url == MINIMAX_CN_CHAT_COMPLETIONS_URL
    assert controller._resolve_api_key("minimax-cn") == "sk-minimax-cn"

    env[ENV_MINIMAX_CN_API_KEY] = ""
    assert controller._resolve_api_key("minimax-cn") == "sk-openai"


@pytest.mark.asyncio
async def test_compaction_generate_summary_uses_alchemy_stream(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "openrouter:openai/gpt-4.1"
    state_manager.session.user_config["env"][ENV_OPENAI_API_KEY] = "sk-openai"

    controller = CompactionController(state_manager=state_manager)
    captured: dict[str, Any] = {}

    class _FakeResponse:
        async def result(self) -> dict[str, Any]:
            return {
                "role": "assistant",
                "content": [{"type": "text", "text": " summary from rust "}],
                "timestamp": None,
                "tool_calls": None,
                "provider": "openrouter",
                "model": "openai/gpt-4.1",
                "usage": {
                    "input": 0,
                    "output": 0,
                    "cache_read": 0,
                    "cache_write": 0,
                    "total_tokens": 0,
                    "cost": {
                        "input": 0.0,
                        "output": 0.0,
                        "cache_read": 0.0,
                        "cache_write": 0.0,
                        "total": 0.0,
                    },
                },
                "error_message": None,
            }

    async def _fake_stream(model: Any, context: Any, options: dict[str, Any]) -> _FakeResponse:
        captured["model"] = model
        captured["context"] = context
        captured["options"] = options
        return _FakeResponse()

    monkeypatch.setattr(compaction_controller, "stream_alchemy_openai_completions", _fake_stream)
    monkeypatch.setattr(compaction_controller, "get_max_tokens", lambda: 321)

    summary = await controller._generate_summary("Summarize this", None)

    assert summary == "summary from rust"
    assert captured["model"].provider == "openrouter"
    assert captured["model"].id == "openai/gpt-4.1"
    assert captured["options"]["api_key"] == "sk-openai"
    assert captured["options"]["max_tokens"] == 321


def test_compaction_controller_raises_when_provider_has_no_api_and_override_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_manager = _build_state_manager(tmp_path, monkeypatch)
    state_manager.session.current_model = "azure:gpt-4.1"

    controller = CompactionController(state_manager=state_manager)

    with pytest.raises(UnsupportedCompactionProviderError, match="azure"):
        controller._build_model()
