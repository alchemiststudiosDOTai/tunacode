"""
Module: tunacode.cli.repl_components.command_parser

Command parsing utilities for the REPL.
"""

import json
import logging

from tunacode.constants import (
    JSON_PARSE_BASE_DELAY,
    JSON_PARSE_MAX_DELAY,
    JSON_PARSE_MAX_RETRIES,
)
from tunacode.exceptions import ValidationError
from tunacode.types import ToolArgs
from tunacode.utils.json_utils import safe_json_parse
from tunacode.utils.retry import retry_json_parse

logger = logging.getLogger(__name__)


def parse_args(args) -> ToolArgs:
    """
    Parse tool arguments from a JSON string or dictionary with retry logic.

    Args:
        args (str or dict): A JSON-formatted string or a dictionary containing tool arguments.

    Returns:
        dict: The parsed arguments.

    Raises:
        ValidationError: If 'args' is not a string or dictionary, or if the string is not valid JSON.
    """
    if isinstance(args, str):
        try:
            # First attempt: Use retry logic for transient failures
            return retry_json_parse(
                args,
                max_retries=JSON_PARSE_MAX_RETRIES,
                base_delay=JSON_PARSE_BASE_DELAY,
                max_delay=JSON_PARSE_MAX_DELAY,
            )
        except json.JSONDecodeError as e:
            # Check if this is an "Extra data" error (concatenated JSON objects)
            if "Extra data" in str(e):
                logger.warning(f"Detected concatenated JSON objects in args: {args[:200]}...")
                try:
                    # Use the new safe JSON parser with concatenation support
                    result = safe_json_parse(args, allow_concatenated=True)
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, list) and result:
                        # Multiple objects - return first one
                        logger.warning("Multiple JSON objects detected, using first object only")
                        return result[0]
                except Exception:
                    # If safe parsing also fails, fall through to original error
                    pass

            # Original error - no recovery possible
            raise ValidationError(f"Invalid JSON: {args}")
    elif isinstance(args, dict):
        return args
    else:
        raise ValidationError(f"Invalid args type: {type(args)}")
