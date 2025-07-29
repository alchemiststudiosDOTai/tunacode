"""Comprehensive unit tests for TunaCode UI key binding handlers."""

from unittest.mock import Mock, patch

import pytest
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings

from tunacode.ui.keybindings import create_key_bindings
from tunacode.core.state import StateManager


class TestCreateKeyBindings:
    """Test suite for create_key_bindings function."""

    def test_create_key_bindings_returns_keybindings_instance(self):
        """Test that create_key_bindings returns a KeyBindings instance."""
        kb = create_key_bindings()
        assert isinstance(kb, KeyBindings)

    def test_create_key_bindings_with_state_manager(self):
        """Test that create_key_bindings accepts a StateManager parameter."""
        mock_state_manager = Mock(spec=StateManager)
        kb = create_key_bindings(state_manager=mock_state_manager)
        assert isinstance(kb, KeyBindings)

    def test_create_key_bindings_without_state_manager(self):
        """Test that create_key_bindings works with None state_manager."""
        kb = create_key_bindings(state_manager=None)
        assert isinstance(kb, KeyBindings)

    def test_key_bindings_has_expected_bindings(self):
        """Test that all expected key bindings are registered."""
        kb = create_key_bindings()

        # Get all registered key combinations
        bindings = []
        for binding in kb.bindings:
            bindings.append(str(binding.keys))

        # Check that our expected bindings are present
        assert any('enter' in binding for binding in bindings)
        assert any('c-o' in binding for binding in bindings)
        assert any('escape' in binding and 'enter' in binding for binding in bindings)
        assert any('escape' in binding for binding in bindings)


class TestEnterKeyBinding:
    """Test suite for Enter key binding behavior."""

    def test_enter_key_calls_validate_and_handle(self):
        """Test that pressing Enter calls validate_and_handle on current buffer."""
        kb = create_key_bindings()

        # Create mock event with current_buffer
        mock_buffer = Mock(spec=Buffer)
        mock_event = Mock()
        mock_event.current_buffer = mock_buffer

        # Find and execute the enter key binding
        for binding in kb.bindings:
            if 'enter' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

        mock_buffer.validate_and_handle.assert_called_once()

    def test_enter_key_binding_exists(self):
        """Test that Enter key binding is properly registered."""
        kb = create_key_bindings()

        # Check that enter binding exists
        enter_bindings = [b for b in kb.bindings if 'enter' in str(b.keys) and len(b.keys) == 1]
        assert len(enter_bindings) >= 1

    def test_enter_key_with_buffer_exception(self):
        """Test Enter key handling when buffer raises an exception."""
        kb = create_key_bindings()

        # Create mock event with failing buffer
        mock_buffer = Mock(spec=Buffer)
        mock_buffer.validate_and_handle.side_effect = Exception("Buffer error")
        mock_event = Mock()
        mock_event.current_buffer = mock_buffer

        # Find and execute the enter key binding - should propagate exception
        with pytest.raises(Exception, match="Buffer error"):
            for binding in kb.bindings:
                if 'enter' in str(binding.keys) and len(binding.keys) == 1:
                    binding.handler(mock_event)
                    break

        mock_buffer.validate_and_handle.assert_called_once()


class TestCtrlOKeyBinding:
    """Test suite for Ctrl+O key binding behavior."""

    def test_ctrl_o_inserts_newline(self):
        """Test that Ctrl+O inserts a newline character."""
        kb = create_key_bindings()

        # Create mock event with current_buffer
        mock_buffer = Mock(spec=Buffer)
        mock_event = Mock()
        mock_event.current_buffer = mock_buffer

        # Find and execute the ctrl+o key binding
        for binding in kb.bindings:
            if 'c-o' in str(binding.keys):
                binding.handler(mock_event)
                break

        mock_buffer.insert_text.assert_called_once_with("\n")

    def test_ctrl_o_key_binding_exists(self):
        """Test that Ctrl+O key binding is properly registered."""
        kb = create_key_bindings()

        # Check that ctrl+o binding exists
        ctrl_o_bindings = [b for b in kb.bindings if 'c-o' in str(b.keys)]
        assert len(ctrl_o_bindings) >= 1

    def test_ctrl_o_with_buffer_exception(self):
        """Test Ctrl+O handling when buffer raises an exception."""
        kb = create_key_bindings()

        # Create mock event with failing buffer
        mock_buffer = Mock(spec=Buffer)
        mock_buffer.insert_text.side_effect = Exception("Insert error")
        mock_event = Mock()
        mock_event.current_buffer = mock_buffer

        # Find and execute the ctrl+o key binding - should propagate exception
        with pytest.raises(Exception, match="Insert error"):
            for binding in kb.bindings:
                if 'c-o' in str(binding.keys):
                    binding.handler(mock_event)
                    break

        mock_buffer.insert_text.assert_called_once_with("\n")


class TestEscapeEnterKeyBinding:
    """Test suite for Escape+Enter key binding behavior."""

    def test_escape_enter_inserts_newline(self):
        """Test that Escape+Enter inserts a newline character."""
        kb = create_key_bindings()

        # Create mock event with current_buffer
        mock_buffer = Mock(spec=Buffer)
        mock_event = Mock()
        mock_event.current_buffer = mock_buffer

        # Find and execute the escape+enter key binding
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and 'enter' in str(binding.keys):
                binding.handler(mock_event)
                break

        mock_buffer.insert_text.assert_called_once_with("\n")

    def test_escape_enter_key_binding_exists(self):
        """Test that Escape+Enter key binding is properly registered."""
        kb = create_key_bindings()

        # Check that escape+enter binding exists
        escape_enter_bindings = [b for b in kb.bindings 
                                 if 'escape' in str(b.keys) and 'enter' in str(b.keys)]
        assert len(escape_enter_bindings) >= 1

    def test_escape_enter_with_buffer_exception(self):
        """Test Escape+Enter handling when buffer raises an exception."""
        kb = create_key_bindings()

        # Create mock event with failing buffer
        mock_buffer = Mock(spec=Buffer)
        mock_buffer.insert_text.side_effect = Exception("Insert error")
        mock_event = Mock()
        mock_event.current_buffer = mock_buffer

        # Find and execute the escape+enter key binding - should propagate exception
        with pytest.raises(Exception, match="Insert error"):
            for binding in kb.bindings:
                if 'escape' in str(binding.keys) and 'enter' in str(binding.keys):
                    binding.handler(mock_event)
                    break

        mock_buffer.insert_text.assert_called_once_with("\n")


class TestEscapeKeyBinding:
    """Test suite for Escape key binding behavior."""

    def test_escape_cancels_current_task_when_exists(self):
        """Test that Escape cancels the current task when it exists and is not done."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_session.current_task = mock_task
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)

        # Create mock event
        mock_event = Mock()

        # Find and execute the escape key binding
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

        mock_task.cancel.assert_called_once()

    def test_escape_does_not_cancel_done_task(self):
        """Test that Escape does not cancel a task that is already done."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_task = Mock()
        mock_task.done.return_value = True
        mock_session.current_task = mock_task
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)

        # Create mock event
        mock_event = Mock()

        # Find and execute the escape key binding
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

        mock_task.cancel.assert_not_called()

    def test_escape_with_no_current_task(self):
        """Test that Escape handles the case when there is no current task."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_session.current_task = None
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)

        # Create mock event
        mock_event = Mock()

        # Find and execute the escape key binding - should not raise
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

    def test_escape_with_no_state_manager(self):
        """Test that Escape handles the case when state_manager is None."""
        kb = create_key_bindings(state_manager=None)

        # Create mock event
        mock_event = Mock()

        # Find and execute the escape key binding - should not raise
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

    def test_escape_key_binding_exists(self):
        """Test that Escape key binding is properly registered."""
        kb = create_key_bindings()

        # Check that escape binding exists (single escape, not escape+enter)
        escape_bindings = [b for b in kb.bindings 
                           if 'escape' in str(b.keys) and len(b.keys) == 1]
        assert len(escape_bindings) >= 1

    @patch('tunacode.ui.keybindings.logger')
    def test_escape_logs_debug_when_canceling_task(self, mock_logger):
        """Test that Escape logs debug message when canceling a task."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_session.current_task = mock_task
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)

        # Create mock event
        mock_event = Mock()

        # Find and execute the escape key binding
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

        mock_logger.debug.assert_called_with("Interrupting current task")

    @patch('tunacode.ui.keybindings.logger')
    def test_escape_logs_debug_outside_task_context(self, mock_logger):
        """Test that Escape logs debug message when pressed outside task context."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_session.current_task = None
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)

        # Create mock event
        mock_event = Mock()

        # Find and execute the escape key binding
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

        mock_logger.debug.assert_called_with("Escape key pressed outside task context")

    def test_escape_handles_task_cancel_exception(self):
        """Test that Escape gracefully handles exceptions when canceling tasks."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_task.cancel.side_effect = Exception("Cancel failed")
        mock_session.current_task = mock_task
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)

        # Create mock event
        mock_event = Mock()

        # Find and execute the escape key binding - should propagate exception
        with pytest.raises(Exception, match="Cancel failed"):
            for binding in kb.bindings:
                if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                    binding.handler(mock_event)
                    break

        mock_task.cancel.assert_called_once()

    def test_escape_with_state_manager_no_session_attribute(self):
        """Test escape handling when state_manager lacks session attribute."""
        mock_state_manager = Mock(spec=StateManager)
        # Remove session attribute to simulate AttributeError
        del mock_state_manager.session

        kb = create_key_bindings(state_manager=mock_state_manager)
        mock_event = Mock()

        # Find and execute escape - should raise AttributeError
        with pytest.raises(AttributeError):
            for binding in kb.bindings:
                if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                    binding.handler(mock_event)
                    break

    def test_escape_with_task_done_exception(self):
        """Test escape handling when task.done() raises an exception."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_task = Mock()
        mock_task.done.side_effect = Exception("Done check failed")
        mock_session.current_task = mock_task
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)
        mock_event = Mock()

        # Find and execute escape - should propagate the exception
        with pytest.raises(Exception, match="Done check failed"):
            for binding in kb.bindings:
                if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                    binding.handler(mock_event)
                    break


class TestKeyBindingsIntegration:
    """Integration tests for key bindings behavior."""

    def test_all_bindings_are_callable(self):
        """Test that all registered key bindings have callable handlers."""
        kb = create_key_bindings()

        for binding in kb.bindings:
            assert callable(binding.handler), f"Handler for {binding.keys} is not callable"

    def test_bindings_count(self):
        """Test that the expected number of bindings are registered."""
        kb = create_key_bindings()

        # We expect exactly 4 bindings: enter, ctrl+o, escape+enter, escape
        assert len(kb.bindings) == 4

    def test_binding_uniqueness(self):
        """Test that key combinations are unique (no conflicts)."""
        kb = create_key_bindings()

        key_combinations = []
        for binding in kb.bindings:
            key_combo = str(binding.keys)
            assert key_combo not in key_combinations, f"Duplicate key binding: {key_combo}"
            key_combinations.append(key_combo)

    def test_state_manager_parameter_propagation(self):
        """Test that state_manager parameter is properly used in escape handler."""
        mock_state_manager = Mock(spec=StateManager)
        mock_session = Mock()
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_session.current_task = mock_task
        mock_state_manager.session = mock_session

        kb = create_key_bindings(state_manager=mock_state_manager)

        # Create mock event
        mock_event = Mock()

        # Execute escape binding to verify state_manager is used
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                binding.handler(mock_event)
                break

        # Verify the state_manager was accessed
        assert mock_state_manager.session.current_task.cancel.called

    def test_different_state_managers_create_independent_bindings(self):
        """Test that different state managers create independent bindings."""
        mock_state_manager_1 = Mock(spec=StateManager)
        mock_state_manager_2 = Mock(spec=StateManager)

        kb1 = create_key_bindings(state_manager=mock_state_manager_1)
        kb2 = create_key_bindings(state_manager=mock_state_manager_2)

        # Both should have the same number of bindings
        assert len(kb1.bindings) == len(kb2.bindings)

        # But they should be different objects
        assert kb1 is not kb2


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_create_key_bindings_with_invalid_state_manager_type(self):
        """Test that create_key_bindings accepts any state_manager type."""
        # Pass different types - should not raise during creation
        kb_string = create_key_bindings(state_manager="invalid")
        kb_int = create_key_bindings(state_manager=42)
        kb_dict = create_key_bindings(state_manager={})

        assert isinstance(kb_string, KeyBindings)
        assert isinstance(kb_int, KeyBindings)
        assert isinstance(kb_dict, KeyBindings)

    def test_all_handlers_with_none_event(self):
        """Test that handlers handle None event by raising appropriate exceptions."""
        kb = create_key_bindings()

        for binding in kb.bindings:
            # All handlers access event attributes, so should raise AttributeError
            with pytest.raises(AttributeError):
                binding.handler(None)

    def test_handlers_with_mock_event_missing_buffer(self):
        """Test handlers when event has no current_buffer attribute."""
        kb = create_key_bindings()
        mock_event = Mock()
        del mock_event.current_buffer  # Remove current_buffer attribute

        for binding in kb.bindings:
            # Skip escape-only binding as it doesn't use current_buffer
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                continue

            # Should raise AttributeError when accessing missing current_buffer
            with pytest.raises(AttributeError):
                binding.handler(mock_event)

    def test_multiple_state_manager_references(self):
        """Test that the same state_manager can be used in multiple keybinding instances."""
        mock_state_manager = Mock(spec=StateManager)

        kb1 = create_key_bindings(state_manager=mock_state_manager)
        kb2 = create_key_bindings(state_manager=mock_state_manager)

        # Both should work with the same state manager
        assert isinstance(kb1, KeyBindings)
        assert isinstance(kb2, KeyBindings)

    def test_keybindings_with_logging_disabled(self):
        """Test that keybindings work when logging is disabled."""
        with patch('tunacode.ui.keybindings.logger') as mock_logger:
            mock_logger.debug = Mock()

            mock_state_manager = Mock(spec=StateManager)
            mock_session = Mock()
            mock_session.current_task = None
            mock_state_manager.session = mock_session

            kb = create_key_bindings(state_manager=mock_state_manager)
            mock_event = Mock()

            # Execute escape binding
            for binding in kb.bindings:
                if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                    binding.handler(mock_event)
                    break

            # Should still call logger.debug
            mock_logger.debug.assert_called_once()


class TestKeyBindingFunctionality:
    """Test the actual functionality of each key binding."""

    def test_enter_binding_function_signature(self):
        """Test that the enter binding function has correct signature."""
        kb = create_key_bindings()

        for binding in kb.bindings:
            if 'enter' in str(binding.keys) and len(binding.keys) == 1:
                # Should accept exactly one parameter (event)
                import inspect
                sig = inspect.signature(binding.handler)
                assert len(sig.parameters) == 1
                break

    def test_ctrl_o_binding_function_signature(self):
        """Test that the ctrl+o binding function has correct signature."""
        kb = create_key_bindings()

        for binding in kb.bindings:
            if 'c-o' in str(binding.keys):
                # Should accept exactly one parameter (event)
                import inspect
                sig = inspect.signature(binding.handler)
                assert len(sig.parameters) == 1
                break

    def test_escape_enter_binding_function_signature(self):
        """Test that the escape+enter binding function has correct signature."""
        kb = create_key_bindings()

        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and 'enter' in str(binding.keys):
                # Should accept exactly one parameter (event)
                import inspect
                sig = inspect.signature(binding.handler)
                assert len(sig.parameters) == 1
                break

    def test_escape_binding_function_signature(self):
        """Test that the escape binding function has correct signature."""
        kb = create_key_bindings()

        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and len(binding.keys) == 1:
                # Should accept exactly one parameter (event)
                import inspect
                sig = inspect.signature(binding.handler)
                assert len(sig.parameters) == 1
                break

    def test_binding_handlers_have_docstrings(self):
        """Test that all binding handlers have descriptive docstrings."""
        kb = create_key_bindings()

        for binding in kb.bindings:
            assert binding.handler.__doc__ is not None
            assert len(binding.handler.__doc__.strip()) > 0

    def test_newline_insertion_behavior(self):
        """Test that newline insertion works consistently across bindings."""
        kb = create_key_bindings()
        mock_buffer = Mock(spec=Buffer)
        mock_event = Mock()
        mock_event.current_buffer = mock_buffer

        # Test ctrl+o
        for binding in kb.bindings:
            if 'c-o' in str(binding.keys):
                binding.handler(mock_event)
                break

        # Test escape+enter
        for binding in kb.bindings:
            if 'escape' in str(binding.keys) and 'enter' in str(binding.keys):
                binding.handler(mock_event)
                break

        # Both should insert newlines
        assert mock_buffer.insert_text.call_count == 2
        mock_buffer.insert_text.assert_called_with("\n")