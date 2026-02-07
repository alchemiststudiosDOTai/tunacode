"""Tests for tunacode.core.agents.agent_components.response_state."""

from tunacode.core.agents.agent_components.response_state import ResponseState
from tunacode.core.types import AgentState


class TestResponseState:
    def test_initial_state(self):
        rs = ResponseState()
        assert rs.current_state == AgentState.USER_INPUT
        assert rs.has_user_response is False
        assert rs.task_completed is False
        assert rs.awaiting_user_guidance is False
        assert rs.has_final_synthesis is False

    def test_transition(self):
        rs = ResponseState()
        rs.transition_to(AgentState.ASSISTANT)
        assert rs.current_state == AgentState.ASSISTANT

    def test_can_transition_to(self):
        rs = ResponseState()
        assert rs.can_transition_to(AgentState.ASSISTANT)
        assert not rs.can_transition_to(AgentState.RESPONSE)

    def test_has_user_response_property(self):
        rs = ResponseState()
        rs.has_user_response = True
        assert rs.has_user_response is True
        rs.has_user_response = False
        assert rs.has_user_response is False

    def test_awaiting_user_guidance_property(self):
        rs = ResponseState()
        rs.awaiting_user_guidance = True
        assert rs.awaiting_user_guidance is True

    def test_has_final_synthesis_property(self):
        rs = ResponseState()
        rs.has_final_synthesis = True
        assert rs.has_final_synthesis is True

    def test_task_completed_setter_syncs_state_machine(self):
        rs = ResponseState()
        rs.transition_to(AgentState.ASSISTANT)
        rs.transition_to(AgentState.RESPONSE)
        rs.task_completed = True
        assert rs.task_completed is True
        assert rs.is_completed()

    def test_task_completed_false_clears_completion(self):
        rs = ResponseState()
        rs.transition_to(AgentState.ASSISTANT)
        rs.transition_to(AgentState.RESPONSE)
        rs.task_completed = True
        rs.task_completed = False
        assert not rs.is_completed()

    def test_set_completion_detected(self):
        rs = ResponseState()
        rs.transition_to(AgentState.ASSISTANT)
        rs.transition_to(AgentState.RESPONSE)
        rs.set_completion_detected(True)
        assert rs.is_completed()

    def test_reset_state(self):
        rs = ResponseState()
        rs.has_user_response = True
        rs.awaiting_user_guidance = True
        rs.has_final_synthesis = True
        rs.transition_to(AgentState.ASSISTANT)
        rs.transition_to(AgentState.RESPONSE)
        rs.task_completed = True
        rs.reset_state()
        assert rs.current_state == AgentState.USER_INPUT
        assert rs.has_user_response is False
        assert rs.task_completed is False
        assert rs.awaiting_user_guidance is False
        assert rs.has_final_synthesis is False

    def test_reset_state_custom_initial(self):
        rs = ResponseState()
        rs.reset_state(AgentState.ASSISTANT)
        assert rs.current_state == AgentState.ASSISTANT
