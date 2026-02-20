from __future__ import annotations

from tunacode.core.session import StateManager


def test_session_defaults_enable_thought_panel() -> None:
    state_manager = StateManager()

    assert state_manager.session.show_thoughts is True


def test_reset_session_restores_thought_panel_default() -> None:
    state_manager = StateManager()
    state_manager.session.show_thoughts = False

    state_manager.reset_session()

    assert state_manager.session.show_thoughts is True
