"""Tests for the message utilities."""

from tunacode.utils.messaging.message_utils import get_message_content


class TestGetMessageContent:
    """Tests for get_message_content()."""

    def test_string_message(self):
        """String messages are returned as-is."""
        message = "Hello, World!"
        assert get_message_content(message) == "Hello, World!"

    def test_empty_string(self):
        """Empty string messages are handled correctly."""
        assert get_message_content("") == ""

    def test_dict_with_content_string(self):
        """Dict with string content key."""
        message = {"content": "Hello from dict"}
        assert get_message_content(message) == "Hello from dict"

    def test_dict_with_content_list(self):
        """Dict with list content key."""
        message = {"content": ["Hello", " ", "World"]}
        # Each item gets joined with a space, so ["Hello", " ", "World"] becomes "Hello   World"
        assert get_message_content(message) == "Hello   World"

    def test_dict_with_simple_content_list(self):
        """Dict with simple list content key."""
        message = {"content": ["Hello", "World"]}
        assert get_message_content(message) == "Hello World"

    def test_dict_with_parts_list(self):
        """Dict with parts key."""
        message = {"parts": ["Part 1", "Part 2"]}
        assert get_message_content(message) == "Part 1 Part 2"

    def test_dict_with_thought(self):
        """Dict with thought key."""
        message = {"thought": "Internal thought"}
        assert get_message_content(message) == "Internal thought"

    def test_object_with_content_string(self):
        """Object with string content attribute."""

        class MockMessage:
            def __init__(self, content):
                self.content = content

        message = MockMessage("Hello from object")
        assert get_message_content(message) == "Hello from object"

    def test_object_with_content_list(self):
        """Object with list content attribute."""

        class MockMessage:
            def __init__(self, content):
                self.content = content

        message = MockMessage(["Hello", " ", "World"])
        # Each item gets joined with a space, so ["Hello", " ", "World"] becomes "Hello   World"
        assert get_message_content(message) == "Hello   World"

    def test_object_with_simple_content_list(self):
        """Object with simple list content attribute."""

        class MockMessage:
            def __init__(self, content):
                self.content = content

        message = MockMessage(["Hello", "World"])
        assert get_message_content(message) == "Hello World"

    def test_object_with_parts_list(self):
        """Object with parts attribute."""

        class MockMessage:
            def __init__(self, parts):
                self.parts = parts

        message = MockMessage(["Part 1", "Part 2"])
        assert get_message_content(message) == "Part 1 Part 2"

    def test_unsupported_message_type(self):
        """Unsupported message types return empty string."""
        message = 12345  # Integer - not supported
        assert get_message_content(message) == ""

    def test_none_message(self):
        """None message returns empty string."""
        assert get_message_content(None) == ""
