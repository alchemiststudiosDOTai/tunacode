from __future__ import annotations

from tunacode.core.session import StateManager

from tunacode.ui.app import TextualReplApp


def test_stream_agent_text_setting_defaults_to_false() -> None:
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {}}
    app = TextualReplApp(state_manager=state_manager)

    assert app._should_stream_agent_text() is False


def test_stream_agent_text_setting_respects_true_value() -> None:
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {"stream_agent_text": True}}
    app = TextualReplApp(state_manager=state_manager)

    assert app._should_stream_agent_text() is True


def test_stream_agent_text_setting_ignores_non_bool_values() -> None:
    state_manager = StateManager()
    state_manager.session.user_config = {"settings": {"stream_agent_text": "true"}}
    app = TextualReplApp(state_manager=state_manager)

    assert app._should_stream_agent_text() is False
