"""Constants shared by the tool dispatcher helpers."""

PART_KIND_TEXT = "text"
PART_KIND_TOOL_CALL = "tool-call"
UNKNOWN_TOOL_NAME = "unknown"

TEXT_PART_JOINER = "\n"
TOOL_NAME_JOINER = ", "
TOOL_NAME_SUFFIX = "..."

TOOL_BATCH_PREVIEW_COUNT = 3
TOOL_NAMES_DISPLAY_LIMIT = 5

INVALID_TOOL_NAME_CHARS = frozenset("<>(){}[]\"'`")
MAX_TOOL_NAME_LENGTH = 50

DEBUG_PREVIEW_MAX_LENGTH = 100
MS_PER_SECOND = 1000

TOOL_FAILURE_TEMPLATE = "{error_type}: {error_message}"
