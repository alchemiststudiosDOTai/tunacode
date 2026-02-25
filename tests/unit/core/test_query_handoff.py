"""Tests for query handoff routing to the main agent."""

from __future__ import annotations

from tunacode.core.agents.main import RequestOrchestrator
from tunacode.core.agents.query_handoff import build_query_handoff
from tunacode.core.session import StateManager


def test_build_query_handoff_routes_debug_queries() -> None:
    handoff = build_query_handoff("Please debug this failing test")

    assert handoff.route == "debug"
    assert "Route: debug" in handoff.message_for_main_agent
    assert "User query:" in handoff.message_for_main_agent


def test_build_query_handoff_passes_commands_through() -> None:
    handoff = build_query_handoff("/compact")

    assert handoff.route == "command"
    assert handoff.message_for_main_agent == "/compact"


def test_request_orchestrator_keeps_user_message_and_handoff_message_distinct() -> None:
    state_manager = StateManager()
    message = "Add typed routing for incoming user query"

    orchestrator = RequestOrchestrator(
        message=message,
        model="openai/gpt-4o",
        state_manager=state_manager,
        tool_callback=None,
        streaming_callback=None,
    )

    assert orchestrator.user_message == message
    assert orchestrator.handoff.route == "build"
    assert orchestrator.message != message
    assert "Route: build" in orchestrator.message
