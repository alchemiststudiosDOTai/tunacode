"""Truncation detection utilities for agent responses."""


def check_for_truncation(combined_content: str) -> bool:
    """Check if content appears to be truncated.

    Args:
        combined_content: The text content to check for truncation

    Returns:
        bool: True if the content appears truncated, False otherwise
    """
    if not combined_content:
        return False

    # Truncation indicators:
    # 1. Ends with "..." or "…" (but not part of a complete sentence)
    # 2. Ends mid-word (no punctuation, space, or complete word)
    # 3. Contains incomplete markdown/code blocks
    # 4. Ends with incomplete parentheses/brackets

    # Check for ellipsis at end suggesting truncation
    if combined_content.endswith(("...", "…")) and not combined_content.endswith(("....", "….")):
        return True

    # Check for mid-word truncation (ends with letters but no punctuation)
    if combined_content and combined_content[-1].isalpha():
        # Look for incomplete words by checking if last "word" seems cut off
        words = combined_content.split()
        if words:
            last_word = words[-1]
            # Common complete word endings vs likely truncations
            complete_endings = (
                "ing",
                "ed",
                "ly",
                "er",
                "est",
                "tion",
                "ment",
                "ness",
                "ity",
                "ous",
                "ive",
                "able",
                "ible",
            )
            incomplete_patterns = (
                "referen",
                "inte",
                "proces",
                "analy",
                "deve",
                "imple",
                "execu",
            )

            if any(last_word.lower().endswith(pattern) for pattern in incomplete_patterns):
                return True
            elif len(last_word) > 2 and not any(
                last_word.lower().endswith(end) for end in complete_endings
            ):
                # Likely truncated if doesn't end with common suffix
                return True

    # Check for unclosed markdown code blocks
    code_block_count = combined_content.count("```")
    if code_block_count % 2 != 0:
        return True

    # Check for unclosed brackets/parentheses (more opens than closes)
    open_brackets = (
        combined_content.count("[") + combined_content.count("(") + combined_content.count("{")
    )
    close_brackets = (
        combined_content.count("]") + combined_content.count(")") + combined_content.count("}")
    )
    return open_brackets > close_brackets
