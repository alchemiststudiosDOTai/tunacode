"""Unit tests for tunacode UI input handling functions."""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.validation import Validator

# Import the module under test
from tunacode.ui.ui_input import formatted_text, input, multiline_input
from tunacode.constants import UI_PROMPT_PREFIX
from tunacode.core.state import StateManager


class TestFormattedText:
    """Test cases for the formatted_text function."""

    def test_formatted_text_simple_string(self):
        """Test formatted_text with a simple string."""
        result = formatted_text("Hello World")
        assert isinstance(result, HTML)
        assert result.value == "Hello World"

    def test_formatted_text_empty_string(self):
        """Test formatted_text with an empty string."""
        result = formatted_text("")
        assert isinstance(result, HTML)
        assert result.value == ""

    def test_formatted_text_with_html_tags(self):
        """Test formatted_text with HTML tags."""
        html_text = "<bold>Bold Text</bold>"
        result = formatted_text(html_text)
        assert isinstance(result, HTML)
        assert result.value == html_text

    def test_formatted_text_with_special_characters(self):
        """Test formatted_text with special characters."""
        special_text = "Test & <script> \"quotes\" 'apostrophes'"
        result = formatted_text(special_text)
        assert isinstance(result, HTML)
        assert result.value == special_text

    def test_formatted_text_with_unicode(self):
        """Test formatted_text with unicode characters."""
        unicode_text = "こんにちは 🌍 ñoël"
        result = formatted_text(unicode_text)
        assert isinstance(result, HTML)
        assert result.value == unicode_text


class TestInputFunction:
    """Test cases for the input function."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create a mock StateManager for testing."""
        return Mock(spec=StateManager)

    @pytest.fixture
    def mock_validator(self):
        """Create a mock Validator for testing."""
        return Mock(spec=Validator)

    @pytest.fixture
    def mock_key_bindings(self):
        """Create a mock KeyBindings for testing."""
        return Mock(spec=KeyBindings)

    @pytest.fixture
    def mock_completer(self):
        """Create a mock completer for testing."""
        return Mock()

    @pytest.fixture
    def mock_lexer(self):
        """Create a mock lexer for testing."""
        return Mock()

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_with_default_parameters(self, mock_prompt_config, mock_prompt_manager):
        """Test input function with minimal default parameters."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "test input"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call the function
        result = await input("test_session")

        # Assertions
        assert result == "test input"
        mock_prompt_config.assert_called_once_with(
            multiline=False,
            is_password=False,
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            timeoutlen=0.05,
        )
        mock_prompt_manager.assert_called_once_with(None)
        mock_manager_instance.get_input.assert_called_once_with(
            "test_session", UI_PROMPT_PREFIX, mock_config_instance
        )

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_with_all_parameters(self, mock_prompt_config, mock_prompt_manager,
                                           mock_state_manager, mock_validator, mock_key_bindings,
                                           mock_completer, mock_lexer):
        """Test input function with all parameters specified."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "full input test"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        placeholder = HTML("Enter text here...")

        # Call the function with all parameters
        result = await input(
            session_key="full_test_session",
            pretext="Custom prompt: ",
            is_password=True,
            validator=mock_validator,
            multiline=True,
            key_bindings=mock_key_bindings,
            placeholder=placeholder,
            completer=mock_completer,
            lexer=mock_lexer,
            timeoutlen=0.1,
            state_manager=mock_state_manager,
        )

        # Assertions
        assert result == "full input test"
        mock_prompt_config.assert_called_once_with(
            multiline=True,
            is_password=True,
            validator=mock_validator,
            key_bindings=mock_key_bindings,
            placeholder=placeholder,
            completer=mock_completer,
            lexer=mock_lexer,
            timeoutlen=0.1,
        )
        mock_prompt_manager.assert_called_once_with(mock_state_manager)
        mock_manager_instance.get_input.assert_called_once_with(
            "full_test_session", "Custom prompt: ", mock_config_instance
        )

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_password_mode(self, mock_prompt_config, mock_prompt_manager):
        """Test input function in password mode."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "hidden_password"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call the function in password mode
        result = await input("password_session", is_password=True)

        # Assertions
        assert result == "hidden_password"
        mock_prompt_config.assert_called_once_with(
            multiline=False,
            is_password=True,
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            timeoutlen=0.05,
        )

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_multiline_mode(self, mock_prompt_config, mock_prompt_manager):
        """Test input function in multiline mode."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "line 1\nline 2\nline 3"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call the function in multiline mode
        result = await input("multiline_session", multiline=True)

        # Assertions
        assert result == "line 1\nline 2\nline 3"
        mock_prompt_config.assert_called_once_with(
            multiline=True,
            is_password=False,
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            timeoutlen=0.05,
        )

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_with_custom_timeout(self, mock_prompt_config, mock_prompt_manager):
        """Test input function with custom timeout length."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "timeout_test"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call the function with custom timeout
        result = await input("timeout_session", timeoutlen=1.0)

        # Assertions
        assert result == "timeout_test"
        mock_prompt_config.assert_called_once_with(
            multiline=False,
            is_password=False,
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            timeoutlen=1.0,
        )

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_with_empty_session_key(self, mock_prompt_config, mock_prompt_manager):
        """Test input function with empty session key."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "empty_key_input"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call the function with empty session key
        result = await input("")

        # Assertions
        assert result == "empty_key_input"
        mock_manager_instance.get_input.assert_called_once_with(
            "", UI_PROMPT_PREFIX, mock_config_instance
        )

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_prompt_manager_exception(self, mock_prompt_config, mock_prompt_manager):
        """Test input function when PromptManager raises an exception."""
        # Setup mocks to raise exception
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.side_effect = Exception("Prompt error")
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call the function and expect exception
        with pytest.raises(Exception, match="Prompt error"):
            await input("error_session")

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_with_zero_timeout(self, mock_prompt_config, mock_prompt_manager):
        """Test input function with zero timeout."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "zero_timeout"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call the function with zero timeout
        result = await input("zero_timeout_session", timeoutlen=0.0)

        # Assertions
        assert result == "zero_timeout"
        mock_prompt_config.assert_called_once_with(
            multiline=False,
            is_password=False,
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            timeoutlen=0.0,
        )


class TestMultilineInputFunction:
    """Test cases for the multiline_input function."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create a mock StateManager for testing."""
        return Mock(spec=StateManager)

    @pytest.fixture
    def mock_command_registry(self):
        """Create a mock command registry for testing."""
        return Mock()

    @patch('tunacode.ui.ui_input.input')
    @patch('tunacode.ui.ui_input.create_key_bindings')
    @patch('tunacode.ui.ui_input.create_completer')
    @patch('tunacode.ui.ui_input.FileReferenceLexer')
    @patch('tunacode.ui.ui_input.formatted_text')
    @pytest.mark.asyncio
    async def test_multiline_input_default_parameters(self, mock_formatted_text, mock_lexer_class,
                                                     mock_create_completer, mock_create_key_bindings,
                                                     mock_input):
        """Test multiline_input with default parameters."""
        # Setup mocks
        mock_input.return_value = "multiline\ntest\ninput"
        mock_kb = Mock()
        mock_create_key_bindings.return_value = mock_kb
        mock_completer = Mock()
        mock_create_completer.return_value = mock_completer
        mock_lexer = Mock()
        mock_lexer_class.return_value = mock_lexer
        mock_placeholder = Mock()
        mock_formatted_text.return_value = mock_placeholder

        # Call the function
        result = await multiline_input()

        # Assertions
        assert result == "multiline\ntest\ninput"
        mock_create_key_bindings.assert_called_once_with(None)
        mock_create_completer.assert_called_once_with(None)
        mock_lexer_class.assert_called_once()
        mock_formatted_text.assert_called_once_with(
            (
                "<darkgrey>"
                "<bold>Enter</bold> to submit • "
                "<bold>Esc + Enter</bold> for new line • "
                "<bold>Esc</bold> to cancel • "
                "<bold>/help</bold> for commands"
                "</darkgrey>"
            )
        )
        mock_input.assert_called_once_with(
            "multiline",
            pretext="> ",
            key_bindings=mock_kb,
            multiline=True,
            placeholder=mock_placeholder,
            completer=mock_completer,
            lexer=mock_lexer,
            state_manager=None,
        )

    @patch('tunacode.ui.ui_input.input')
    @patch('tunacode.ui.ui_input.create_key_bindings')
    @patch('tunacode.ui.ui_input.create_completer')
    @patch('tunacode.ui.ui_input.FileReferenceLexer')
    @patch('tunacode.ui.ui_input.formatted_text')
    @pytest.mark.asyncio
    async def test_multiline_input_with_state_manager_and_command_registry(
        self, mock_formatted_text, mock_lexer_class, mock_create_completer,
        mock_create_key_bindings, mock_input, mock_state_manager, mock_command_registry
    ):
        """Test multiline_input with state manager and command registry."""
        # Setup mocks
        mock_input.return_value = "advanced\nmultiline\ninput"
        mock_kb = Mock()
        mock_create_key_bindings.return_value = mock_kb
        mock_completer = Mock()
        mock_create_completer.return_value = mock_completer
        mock_lexer = Mock()
        mock_lexer_class.return_value = mock_lexer
        mock_placeholder = Mock()
        mock_formatted_text.return_value = mock_placeholder

        # Call the function with parameters
        result = await multiline_input(
            state_manager=mock_state_manager,
            command_registry=mock_command_registry
        )

        # Assertions
        assert result == "advanced\nmultiline\ninput"
        mock_create_key_bindings.assert_called_once_with(mock_state_manager)
        mock_create_completer.assert_called_once_with(mock_command_registry)
        mock_input.assert_called_once_with(
            "multiline",
            pretext="> ",
            key_bindings=mock_kb,
            multiline=True,
            placeholder=mock_placeholder,
            completer=mock_completer,
            lexer=mock_lexer,
            state_manager=mock_state_manager,
        )

    @patch('tunacode.ui.ui_input.input')
    @patch('tunacode.ui.ui_input.create_key_bindings')
    @patch('tunacode.ui.ui_input.create_completer')
    @patch('tunacode.ui.ui_input.FileReferenceLexer')
    @patch('tunacode.ui.ui_input.formatted_text')
    @pytest.mark.asyncio
    async def test_multiline_input_empty_result(self, mock_formatted_text, mock_lexer_class,
                                               mock_create_completer, mock_create_key_bindings,
                                               mock_input):
        """Test multiline_input returning empty result."""
        # Setup mocks
        mock_input.return_value = ""
        mock_kb = Mock()
        mock_create_key_bindings.return_value = mock_kb
        mock_completer = Mock()
        mock_create_completer.return_value = mock_completer
        mock_lexer = Mock()
        mock_lexer_class.return_value = mock_lexer
        mock_placeholder = Mock()
        mock_formatted_text.return_value = mock_placeholder

        # Call the function
        result = await multiline_input()

        # Assertions
        assert result == ""

    @patch('tunacode.ui.ui_input.input')
    @patch('tunacode.ui.ui_input.create_key_bindings')
    @patch('tunacode.ui.ui_input.create_completer')
    @patch('tunacode.ui.ui_input.FileReferenceLexer')
    @patch('tunacode.ui.ui_input.formatted_text')
    @pytest.mark.asyncio
    async def test_multiline_input_with_exception_in_dependencies(
        self, mock_formatted_text, mock_lexer_class, mock_create_completer,
        mock_create_key_bindings, mock_input
    ):
        """Test multiline_input when dependencies raise exceptions."""
        # Setup mocks to raise exception
        mock_create_key_bindings.side_effect = Exception("Key binding error")

        # Call the function and expect exception
        with pytest.raises(Exception, match="Key binding error"):
            await multiline_input()

    @patch('tunacode.ui.ui_input.input')
    @patch('tunacode.ui.ui_input.create_key_bindings')
    @patch('tunacode.ui.ui_input.create_completer')
    @patch('tunacode.ui.ui_input.FileReferenceLexer')
    @patch('tunacode.ui.ui_input.formatted_text')
    @pytest.mark.asyncio
    async def test_multiline_input_with_input_exception(
        self, mock_formatted_text, mock_lexer_class, mock_create_completer,
        mock_create_key_bindings, mock_input
    ):
        """Test multiline_input when input function raises exception."""
        # Setup mocks
        mock_kb = Mock()
        mock_create_key_bindings.return_value = mock_kb
        mock_completer = Mock()
        mock_create_completer.return_value = mock_completer
        mock_lexer = Mock()
        mock_lexer_class.return_value = mock_lexer
        mock_placeholder = Mock()
        mock_formatted_text.return_value = mock_placeholder

        # Make input raise exception
        mock_input.side_effect = Exception("Input error")

        # Call the function and expect exception
        with pytest.raises(Exception, match="Input error"):
            await multiline_input()

    @patch('tunacode.ui.ui_input.input')
    @patch('tunacode.ui.ui_input.create_key_bindings')
    @patch('tunacode.ui.ui_input.create_completer')
    @patch('tunacode.ui.ui_input.FileReferenceLexer')
    @patch('tunacode.ui.ui_input.formatted_text')
    @pytest.mark.asyncio
    async def test_multiline_input_placeholder_text_format(self, mock_formatted_text, mock_lexer_class,
                                                          mock_create_completer, mock_create_key_bindings,
                                                          mock_input):
        """Test multiline_input placeholder text formatting."""
        # Setup mocks
        mock_input.return_value = "test"
        mock_kb = Mock()
        mock_create_key_bindings.return_value = mock_kb
        mock_completer = Mock()
        mock_create_completer.return_value = mock_completer
        mock_lexer = Mock()
        mock_lexer_class.return_value = mock_lexer
        mock_placeholder = Mock()
        mock_formatted_text.return_value = mock_placeholder

        # Call the function
        await multiline_input()

        # Verify the exact placeholder text format
        expected_placeholder_text = (
            "<darkgrey>"
            "<bold>Enter</bold> to submit • "
            "<bold>Esc + Enter</bold> for new line • "
            "<bold>Esc</bold> to cancel • "
            "<bold>/help</bold> for commands"
            "</darkgrey>"
        )
        mock_formatted_text.assert_called_once_with(expected_placeholder_text)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_with_none_values(self, mock_prompt_config, mock_prompt_manager):
        """Test input function with None values for optional parameters."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "none_test"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call with explicit None values
        result = await input(
            "none_session",
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            state_manager=None,
        )

        # Assertions
        assert result == "none_test"
        mock_prompt_config.assert_called_once_with(
            multiline=False,
            is_password=False,
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            timeoutlen=0.05,
        )

    @pytest.mark.asyncio
    async def test_formatted_text_with_very_long_string(self):
        """Test formatted_text with very long string."""
        long_text = "A" * 10000
        result = formatted_text(long_text)
        assert isinstance(result, HTML)
        assert result.value == long_text
        assert len(result.value) == 10000

    @patch('tunacode.ui.ui_input.PromptManager')
    @patch('tunacode.ui.ui_input.PromptConfig')
    @pytest.mark.asyncio
    async def test_input_with_negative_timeout(self, mock_prompt_config, mock_prompt_manager):
        """Test input function with negative timeout."""
        # Setup mocks
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_input.return_value = "negative_timeout"
        mock_prompt_manager.return_value = mock_manager_instance

        mock_config_instance = Mock()
        mock_prompt_config.return_value = mock_config_instance

        # Call with negative timeout
        result = await input("negative_session", timeoutlen=-1.0)

        # Assertions
        assert result == "negative_timeout"
        mock_prompt_config.assert_called_once_with(
            multiline=False,
            is_password=False,
            validator=None,
            key_bindings=None,
            placeholder=None,
            completer=None,
            lexer=None,
            timeoutlen=-1.0,
        )


if __name__ == "__main__":
    pytest.main([__file__])