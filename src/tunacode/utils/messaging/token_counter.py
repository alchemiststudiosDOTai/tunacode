"""Token counting utility using fast character-based heuristic."""


def estimate_tokens(text: str, model_name: str | None = None) -> int:
    """Estimate token count using character-based heuristic.

    Uses len(text) // 4 which is roughly accurate for English text
    and has O(1) overhead. Good enough for status bar estimates.

    Args:
        text: The text to count tokens for.
        model_name: Unused, kept for API compatibility.

    Returns:
        The estimated number of tokens.
    """
    if not text:
        return 0
    return len(text) // 4
