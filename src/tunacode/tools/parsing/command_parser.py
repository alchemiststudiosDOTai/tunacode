"""Module: tunacode.tools.parsing.command_parser

Command parsing utilities for the Textual REPL.

Performance note:
Tool argument JSON parsing must fail fast. Retrying JSON decoding (with backoff) is
wasted time because malformed JSON will not become valid with retries.
"""

import json
from typing import Any

from tunacode.exceptions import ValidationError

from tunacode.tools.parsing.json_utils import safe_json_parse

ARG_ERROR_PREVIEW_LIMIT: int = 200


def _preview_json(value: str) -> str:
    preview = value[:ARG_ERROR_PREVIEW_LIMIT]
    if len(value) > ARG_ERROR_PREVIEW_LIMIT:
        return f"{preview}..."
    return preview


def _parse_json_args(args: str) -> dict[str, Any]:
    try:
        parsed = json.loads(args)
    except json.JSONDecodeError as exc:
        # Common model failure mode: concatenated objects like {..}{..}
        if "Extra data" in str(exc):
            try:
                parsed_concat = safe_json_parse(args, allow_concatenated=True)
            except Exception:
                raise ValidationError(f"Invalid JSON: {_preview_json(args)}") from exc

            if isinstance(parsed_concat, dict):
                return parsed_concat

        raise ValidationError(f"Invalid JSON: {_preview_json(args)}") from exc

    if not isinstance(parsed, dict):
        raise ValidationError(f"Invalid JSON: expected object, got {type(parsed).__name__}")

    return parsed


async def parse_args(args: Any) -> dict[str, Any]:
    """Parse tool arguments from a JSON string or dict.

    Args:
        args: Either a JSON string or a dict containing tool arguments.

    Returns:
        Parsed arguments as a dict.

    Raises:
        ValidationError: If args is not a string/dict, or the JSON is invalid.
    """
    if isinstance(args, dict):
        return args

    if isinstance(args, str):
        return _parse_json_args(args)

    raise ValidationError(f"Invalid args type: {type(args)}")
