"""Tests for tunacode.core.agents.agent_components.result_wrapper."""

import pytest

from tunacode.core.agents.agent_components.result_wrapper import (
    AgentRunWithState,
    AgentRunWrapper,
    SimpleResult,
)


class TestSimpleResult:
    def test_stores_output(self):
        result = SimpleResult("hello")
        assert result.output == "hello"


class TestAgentRunWrapper:
    def test_result_returns_fallback(self):
        class FakeRun:
            result = "original"
            data = "wrapped_data"

        wrapper = AgentRunWrapper(FakeRun(), "fallback_result")
        assert wrapper.result == "fallback_result"

    def test_delegates_to_wrapped(self):
        class FakeRun:
            data = "wrapped_data"

        wrapper = AgentRunWrapper(FakeRun(), "fallback")
        assert wrapper.data == "wrapped_data"

    def test_response_state_accessible(self):
        class FakeRun:
            pass

        wrapper = AgentRunWrapper(FakeRun(), "fallback", response_state="state_obj")
        assert wrapper.response_state == "state_obj"

    def test_missing_attr_raises(self):
        class FakeRun:
            pass

        wrapper = AgentRunWrapper(FakeRun(), "fallback")
        with pytest.raises(AttributeError):
            _ = wrapper.nonexistent_attr


class TestAgentRunWithState:
    def test_delegates_to_wrapped(self):
        class FakeRun:
            data = "value"
            result = "run_result"

        wrapper = AgentRunWithState(FakeRun())
        assert wrapper.data == "value"
        assert wrapper.result == "run_result"

    def test_response_state_accessible(self):
        class FakeRun:
            pass

        wrapper = AgentRunWithState(FakeRun(), response_state="state")
        assert wrapper.response_state == "state"

    def test_default_response_state_is_none(self):
        class FakeRun:
            pass

        wrapper = AgentRunWithState(FakeRun())
        assert wrapper.response_state is None

    def test_missing_attr_raises(self):
        class FakeRun:
            pass

        wrapper = AgentRunWithState(FakeRun())
        with pytest.raises(AttributeError):
            _ = wrapper.nonexistent_attr
