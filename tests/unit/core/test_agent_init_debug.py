from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from tunacode.core.agents.agent_components import agent_config
from tunacode.core.session import StateManager


def test_get_or_create_agent_emits_init_phase_lifecycle_logs(
    monkeypatch,
) -> None:
    lifecycle_messages: list[str] = []
    logger = MagicMock()
    logger.lifecycle.side_effect = lifecycle_messages.append

    class FakeAgent:
        def __init__(self, options):
            self.options = options
            self._state = SimpleNamespace(system_prompt=None)

        def set_system_prompt(self, system_prompt: str) -> None:
            self._state.system_prompt = system_prompt

        def set_model(self, model: object) -> None:
            self.model = model

        def set_tools(self, tools: list[object]) -> None:
            self.tools = tools

    monkeypatch.setattr(agent_config, "get_logger", lambda: logger)
    monkeypatch.setattr(agent_config, "Agent", FakeAgent)
    monkeypatch.setattr(agent_config, "get_cached_models_registry", lambda: None)
    monkeypatch.setattr(agent_config, "load_models_registry", lambda: {})
    monkeypatch.setattr(agent_config, "list_skill_summaries", lambda: [])
    monkeypatch.setattr(agent_config, "resolve_selected_skills", lambda _names: [])
    monkeypatch.setattr(agent_config, "load_system_prompt", lambda _base_path, model=None: "SYS")
    monkeypatch.setattr(agent_config, "load_tunacode_context", lambda: "CTX")
    monkeypatch.setattr(agent_config, "_build_tools", lambda **kwargs: [])
    monkeypatch.setattr(agent_config, "_build_tinyagent_model", lambda model, config: object())

    state_manager = StateManager()
    state_manager.session.selected_skill_names = []
    state_manager.session.user_config["settings"]["max_tokens"] = 4096

    agent = agent_config.get_or_create_agent(state_manager.session.current_model, state_manager)

    assert agent._state.system_prompt.startswith("SYSCTX")
    assert any(message.startswith("Init: models_registry ") for message in lifecycle_messages)
    assert any(message.startswith("Init: available_skills ") for message in lifecycle_messages)
    assert any(message.startswith("Init: selected_skills ") for message in lifecycle_messages)
    assert any(message.startswith("Init: skills_prompt ") for message in lifecycle_messages)
    assert any(message.startswith("Init: agent_build ") for message in lifecycle_messages)
