"""Messaging utilities: canonical adapters and token counting."""

# Canonical message adapter
from tunacode.utils.messaging.adapter import (
    _get_attr,
    _get_parts,
    find_dangling_tool_calls,
    from_canonical,
    from_canonical_list,
    get_content,
    get_tool_call_ids,
    get_tool_return_ids,
    to_canonical,
    to_canonical_list,
)
from tunacode.utils.messaging.token_counter import estimate_tokens

__all__ = [
    "estimate_tokens",
    # Canonical adapter
    "to_canonical",
    "to_canonical_list",
    "from_canonical",
    "from_canonical_list",
    "get_content",
    "get_tool_call_ids",
    "get_tool_return_ids",
    "find_dangling_tool_calls",
    # Low-level accessors (for internal modules)
    "_get_attr",
    "_get_parts",
]
