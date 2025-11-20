"""Tests for agent HTTP client setup and request delay configuration."""

from __future__ import annotations

import copy

import httpx
import pytest
from pydantic_ai.retries import AsyncTenacityTransport

from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
from tunacode.core.agents.agent_components import agent_config as ac
from tunacode.core.state import StateManager


@pytest.fixture(autouse=True)
def clear_agent_caches():
    """Ensure agent caches do not leak across tests."""
    ac.clear_all_caches()
    yield
    ac.clear_all_caches()


@pytest.fixture
def state_manager() -> StateManager:
    """Provide a fresh StateManager with default user config."""
    manager = StateManager()
    manager.session.user_config = copy.deepcopy(DEFAULT_USER_CONFIG)
    return manager


def test_request_delay_default_zero(state_manager: StateManager) -> None:
    """Request delay should default to zero (no throttling)."""
    assert state_manager.session.user_config["settings"]["request_delay"] == 0.0


@pytest.mark.asyncio
async def test_request_delay_hook_applies_sleep(
    monkeypatch: pytest.MonkeyPatch, state_manager: StateManager
) -> None:
    """Configure a request delay and ensure the HTTP client awaits it per request."""
    state_manager.session.user_config["settings"]["request_delay"] = 0.25
    captured_hooks: dict = {}

    class RecordingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured_hooks.update(kwargs.get("event_hooks") or {})
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ac, "AsyncClient", RecordingAsyncClient)
    monkeypatch.setattr(ac, "asyncio", __import__("asyncio"), raising=False)
    ac.get_or_create_agent("openai:gpt-4.1", state_manager)

    request_hooks = captured_hooks.get("request")
    assert request_hooks, "Expected a request hook to enforce request_delay"

    hook = request_hooks[0]
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(ac.asyncio, "sleep", fake_sleep)

    await hook(httpx.Request("GET", "http://example.com"))

    assert sleep_calls == [0.25]


def test_http_client_uses_retry_transport_by_default(
    monkeypatch: pytest.MonkeyPatch, state_manager: StateManager
) -> None:
    """Golden baseline: HTTP client uses retry transport without request hooks."""
    captured_kwargs: dict = {}

    class RecordingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            captured_kwargs.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ac, "AsyncClient", RecordingAsyncClient)

    ac.get_or_create_agent("openai:gpt-4.1", state_manager)

    transport = captured_kwargs.get("transport")
    assert isinstance(transport, AsyncTenacityTransport)
    assert captured_kwargs.get("event_hooks") in (None, {})
