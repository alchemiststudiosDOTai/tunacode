"""Module: tunacode.cli.command_parser

Command parsing utilities for the Textual REPL."""

import json
import logging

from tunacode.constants import (
    JSON_PARSE_BASE_DELAY,
    JSON_PARSE_MAX_DELAY,
    JSON_PARSE_MAX_RETRIES,
)
from tunacode.exceptions import ValidationError
from tunacode.types import ToolArgs
from tunacode.utils.parsing.json_utils import safe_json_parse
from tunacode.utils.parsing.retry import retry_json_parse

logger = logging.getLogger(__name__)


def parse_args(args) -> ToolArgs:
    """
    Parse tool arguments from a JSON string or dictionary with retry logic.

    Args:
        args (str or dict): A JSON-formatted string or a dictionary containing tool arguments.

    Returns:
        dict: The parsed arguments.

    Raises:
        ValidationError: If 'args' is not a string or dictionary, or if the string
        is not valid JSON.
    """
    if isinstance(args, str):
        try:
            return retry_json_parse(
                args,
                max_retries=JSON_PARSE_MAX_RETRIES,
                base_delay=JSON_PARSE_BASE_DELAY,
                max_delay=JSON_PARSE_MAX_DELAY,
            )
        except json.JSONDecodeError as e:
            if "Extra data" in str(e):
                logger.warning(f"Detected concatenated JSON objects in args: {args[:200]}...")
                try:
                    result = safe_json_parse(args, allow_concatenated=True)
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, list) and result:
                        logger.warning("Multiple JSON objects detected, using first object only")
                        return result[0]
                except Exception:
                    pass

            raise ValidationError(f"Invalid JSON: {args}") from e
    elif isinstance(args, dict):
        return args
    else:
        raise ValidationError(f"Invalid args type: {type(args)}")
