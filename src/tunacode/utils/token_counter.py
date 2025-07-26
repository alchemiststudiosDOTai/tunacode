"""Token counting utility using tiktoken for accurate, offline token estimation."""

import logging
from functools import lru_cache
from typing import Optional

# Get logger for this module
logger = logging.getLogger(__name__)

# Cache for tokenizer encodings
_encoding_cache = {}


@lru_cache(maxsize=8)
def get_encoding(model_name: str):
    """Get the appropriate tiktoken encoding for a model.

    Args:
        model_name: The model name in format "provider:model"

    Returns:
        A tiktoken encoding instance
    """
    try:
        import tiktoken
    except ImportError:
        logger.warning("tiktoken not available, falling back to character estimation")
        return None

    # Extract the model part from "provider:model" format
    if ":" in model_name:
        provider, model = model_name.split(":", 1)
    else:
        provider, model = "unknown", model_name

    # Map common models to their tiktoken encodings
    if provider == "openai":
        if "gpt-4" in model:
            encoding_name = "cl100k_base"  # GPT-4 encoding
        elif "gpt-3.5" in model:
            encoding_name = "cl100k_base"  # GPT-3.5-turbo encoding
        else:
            encoding_name = "cl100k_base"  # Default for newer models
    elif provider == "anthropic":
        # Claude models use similar tokenization to GPT-4
        encoding_name = "cl100k_base"
    else:
        # Default encoding for unknown models
        encoding_name = "cl100k_base"

    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception as e:
        logger.error(f"Error loading tiktoken encoding '{encoding_name}': {e}")
        return None


def estimate_tokens(text: str, model_name: Optional[str] = None) -> int:
    """
    Estimate token count using tiktoken for accurate results.

    Args:
        text: The text to count tokens for.
        model_name: Optional model name for model-specific tokenization.

    Returns:
        The estimated number of tokens.
    """
    if not text:
        return 0

    # Try tiktoken first if model is specified
    if model_name:
        encoding = get_encoding(model_name)
        if encoding:
            try:
                return len(encoding.encode(text))
            except Exception as e:
                logger.error(f"Error counting tokens with tiktoken: {e}")

    # Fallback to character-based estimation
    # This is roughly accurate for English text
    return len(text) // 4


def format_token_count(count: int) -> str:
    """Format token count for display with full precision."""
    if count >= 1_000_000:
        return f"{count:,}"
    elif count >= 1000:
        return f"{count:,}"
    return str(count)
