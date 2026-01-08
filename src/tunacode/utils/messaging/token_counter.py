"""Token counting utility using a lightweight heuristic."""

CHARS_PER_TOKEN: int = 4


def estimate_tokens(text: str, model_name: str | None = None) -> int:
    """
    Estimate token count using a simple character heuristic.

    Args:
        text: The text to count tokens for.
        model_name: Optional model name (unused).

    Returns:
        The estimated number of tokens.
    """
    if not text:
        return 0

    return len(text) // CHARS_PER_TOKEN
