"""Token counting utility using the Google Generative AI API."""

import logging
import os

from google import genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using the Google Generative AI API.

    Args:
        text: The text to count tokens for.

    Returns:
        The estimated number of tokens.
    """
    if not text:
        return 0

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.count_tokens(model="gemini-2.0-flash", contents=[text])
        return response.total_tokens
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        return len(text) // 4


def format_token_count(count: int) -> str:
    """Format token count for display."""
    if int(count) >= 1000:
        return f"{int(count) // 1000}k"
    return str(count)
