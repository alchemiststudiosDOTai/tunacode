def reverse_string(text: str) -> str:
    """
    Reverses a string.

    Args:
        text: Input string to reverse

    Returns:
        Reversed string

    Note: This implementation has a bug with Unicode characters!
    """
    if not text:
        return text

    # BUG: This naive reversal breaks Unicode surrogate pairs and combining characters
    return text[::-1]


def is_palindrome(text: str) -> bool:
    """
    Checks if a string is a palindrome (ignores case and spaces).

    Args:
        text: Input string to check

    Returns:
        True if palindrome, False otherwise
    """
    if not text:
        return True

    # Clean the text
    cleaned = ''.join(text.lower().split())

    # Use our reverse function (which has the Unicode bug)
    return cleaned == reverse_string(cleaned)
