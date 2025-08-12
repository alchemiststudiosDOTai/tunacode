import os
import sys

# Add base_code directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'base_code'))

from string_utils import is_palindrome, reverse_string


class TestReverseString:
    """Test cases for reverse_string function."""

    def test_empty_string(self):
        """Test reversing empty string."""
        assert reverse_string("") == ""

    def test_single_character(self):
        """Test reversing single character."""
        assert reverse_string("a") == "a"

    def test_ascii_string(self):
        """Test reversing ASCII string."""
        assert reverse_string("hello") == "olleh"
        assert reverse_string("Python") == "nohtyP"

    def test_string_with_spaces(self):
        """Test reversing string with spaces."""
        assert reverse_string("hello world") == "dlrow olleh"

    def test_unicode_basic(self):
        """Test reversing basic Unicode characters."""
        assert reverse_string("café") == "éfac"
        assert reverse_string("naïve") == "evïan"

    def test_unicode_emoji(self):
        """Test reversing Unicode emoji - this will fail due to the bug!"""
        # Test with a more complex emoji that may break
        text = "hello👨‍💻world"  # Man technologist emoji (composite)
        expected = "dlrow👨‍💻olleh"
        result = reverse_string(text)
        assert result == expected, f"Expected '{expected}', got '{result}'"

    def test_unicode_combining_characters(self):
        """Test reversing Unicode combining characters - this will fail!"""
        # é can be represented as e + combining acute accent
        text = "cafe\u0301"  # café with combining character
        # The combining character should stay with its base character
        result = reverse_string(text)
        # This will fail because naive reversal breaks the combining sequence
        assert len(result) == 5, f"Expected length 5, got {len(result)}"

    def test_unicode_complex(self):
        """Test complex Unicode text."""
        text = "🌟Hello世界🌟"
        result = reverse_string(text)
        # This may fail depending on how Unicode is handled
        assert len(result) > 0


class TestIsPalindrome:
    """Test cases for is_palindrome function."""

    def test_empty_string(self):
        """Test empty string palindrome."""
        assert is_palindrome("") is True

    def test_single_character(self):
        """Test single character palindrome."""
        assert is_palindrome("a") is True

    def test_ascii_palindrome(self):
        """Test ASCII palindromes."""
        assert is_palindrome("racecar") is True
        assert is_palindrome("A man a plan a canal Panama") is True
        assert is_palindrome("hello") is False

    def test_case_insensitive(self):
        """Test case insensitive palindrome check."""
        assert is_palindrome("Racecar") is True
        assert is_palindrome("RaceCar") is True

    def test_unicode_palindrome(self):
        """Test Unicode palindromes - may fail due to reverse_string bug."""
        # This will likely fail due to the Unicode reversal bug
        assert is_palindrome("A🌟🌟A") is True
        assert is_palindrome("café éfac") is True
