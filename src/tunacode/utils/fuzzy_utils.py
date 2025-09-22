"""Shared fuzzy matching utilities.

Minimal helper to provide consistent fuzzy matching behavior across
components (commands, file completers, etc.) without introducing new
dependencies. Reuses difflib.get_close_matches with a default cutoff of 0.75
matching the command registry behavior.
"""

from difflib import get_close_matches
from typing import List, Sequence


def find_fuzzy_matches(
    query: str,
    choices: Sequence[str],
    *,
    n: int = 5,
    cutoff: float = 0.75,
) -> List[str]:
    """Return up to ``n`` fuzzy matches from ``choices`` for ``query``.

    The return order is the order produced by ``difflib.get_close_matches``.
    Matching is case-insensitive; original casing is preserved in the result.
    """
    if not query or not choices:
        return []

    # Map lower-case to original to do case-insensitive matching while
    # returning original items.
    lower_to_original = {c.lower(): c for c in choices}
    candidates = list(lower_to_original.keys())
    matches_lower = get_close_matches(query.lower(), candidates, n=n, cutoff=cutoff)
    return [lower_to_original[m] for m in matches_lower]
