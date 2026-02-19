from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tunacode.core.agents.agent_components import agent_config
from tunacode.core.session import StateManager

MINIMAX_CODING_PLAN_MODEL = "minimax-coding-plan:MiniMax-M2.1"
MINIMAX_API_KEY_ENV = "MINIMAX_API_KEY"
MINIMAX_API_KEY_VALUE = "sk-minimax"
MINIMAX_CHAT_COMPLETIONS_URL = "https://api.minimax.io/v1/chat/completions"
MINIMAX_ALCHEMY_API = "minimax-completions"


class _FakeResponse:
    def __init__(self) -> None:
        self._done_emitted = False

    def __aiter__(self) -> _FakeResponse:
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._done_emitted:
            raise StopAsyncIteration

        self._done_emitted = True
        return {"type": "done"}

    async def result(self) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": "ok"}],
            "timestamp": None,
        }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_minimax_coding_plan_execution_path_uses_minimax_alchemy_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    state_manager = StateManager()
    session = state_manager.session
    session.current_model = MINIMAX_CODING_PLAN_MODEL
    session.user_config["env"][MINIMAX_API_KEY_ENV] = MINIMAX_API_KEY_VALUE

    captured: dict[str, Any] = {}

    async def _fake_stream(model: Any, context: Any, options: dict[str, Any]) -> _FakeResponse:
        captured["model"] = model
        captured["context"] = context
        captured["options"] = options
        return _FakeResponse()

    monkeypatch.setattr(agent_config, "stream_alchemy_openai_completions", _fake_stream)
    monkeypatch.setattr(agent_config, "load_system_prompt", lambda _base_path, model=None: "")
    monkeypatch.setattr(agent_config, "load_tunacode_context", lambda: "")

    agent = agent_config.get_or_create_agent(MINIMAX_CODING_PLAN_MODEL, state_manager)
    response_text = await agent.prompt_text("Reply with ok")

    assert response_text == "ok"

    model = captured["model"]
    assert model.provider == "minimax-coding-plan"
    assert model.id == "MiniMax-M2.1"
    assert model.api == MINIMAX_ALCHEMY_API
    assert model.base_url == MINIMAX_CHAT_COMPLETIONS_URL

    options = captured["options"]
    assert options["api_key"] == MINIMAX_API_KEY_VALUE
