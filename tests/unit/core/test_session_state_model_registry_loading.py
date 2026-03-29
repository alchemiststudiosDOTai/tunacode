from __future__ import annotations

from tunacode.infrastructure.cache import clear_all

from tunacode.core.session import StateManager


def test_state_manager_loads_default_model_context_window_on_cold_cache(
    tmp_path,
    monkeypatch,
) -> None:
    home_dir = tmp_path / "home"

    clear_all()
    try:
        monkeypatch.setenv("HOME", str(home_dir))
        state_manager = StateManager()

        assert state_manager.session.current_model == "openrouter:openai/gpt-4.1"
        assert state_manager.session.conversation.max_tokens == 1047576
    finally:
        clear_all()
