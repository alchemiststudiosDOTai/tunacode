"""Core facade for shared constants used by the UI."""

from __future__ import annotations

# Re-exports for UI layer access (noqa: F401)
from tunacode.constants import APP_NAME as APP_NAME  # noqa: F401
from tunacode.constants import APP_VERSION as APP_VERSION  # noqa: F401
from tunacode.constants import BOX_HORIZONTAL as BOX_HORIZONTAL  # noqa: F401
from tunacode.constants import ENV_OPENAI_BASE_URL as ENV_OPENAI_BASE_URL  # noqa: F401
from tunacode.constants import HOOK_ARROW_PREFIX as HOOK_ARROW_PREFIX  # noqa: F401
from tunacode.constants import MAX_CALLBACK_CONTENT as MAX_CALLBACK_CONTENT  # noqa: F401
from tunacode.constants import MAX_PANEL_LINES as MAX_PANEL_LINES  # noqa: F401
from tunacode.constants import (
    MAX_SEARCH_RESULTS_DISPLAY as MAX_SEARCH_RESULTS_DISPLAY,  # noqa: F401
)
from tunacode.constants import MIN_TOOL_PANEL_LINE_WIDTH as MIN_TOOL_PANEL_LINE_WIDTH  # noqa: F401
from tunacode.constants import MIN_VIEWPORT_LINES as MIN_VIEWPORT_LINES  # noqa: F401
from tunacode.constants import (
    MODEL_PICKER_UNFILTERED_LIMIT as MODEL_PICKER_UNFILTERED_LIMIT,  # noqa: F401
)
from tunacode.constants import RESOURCE_BAR_COST_FORMAT as RESOURCE_BAR_COST_FORMAT  # noqa: F401
from tunacode.constants import RESOURCE_BAR_SEPARATOR as RESOURCE_BAR_SEPARATOR  # noqa: F401
from tunacode.constants import RICHLOG_CLASS_PAUSED as RICHLOG_CLASS_PAUSED  # noqa: F401
from tunacode.constants import RICHLOG_CLASS_STREAMING as RICHLOG_CLASS_STREAMING  # noqa: F401
from tunacode.constants import SEPARATOR_WIDTH as SEPARATOR_WIDTH  # noqa: F401
from tunacode.constants import (
    SYNTAX_LINE_NUMBER_PADDING as SYNTAX_LINE_NUMBER_PADDING,  # noqa: F401
)
from tunacode.constants import (
    SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH as SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH,  # noqa: F401
)
from tunacode.constants import (
    TOOL_PANEL_HORIZONTAL_INSET as TOOL_PANEL_HORIZONTAL_INSET,  # noqa: F401
)
from tunacode.constants import TOOL_PANEL_WIDTH_DEBUG as TOOL_PANEL_WIDTH_DEBUG  # noqa: F401
from tunacode.constants import TOOL_VIEWPORT_LINES as TOOL_VIEWPORT_LINES  # noqa: F401
from tunacode.constants import UI_COLORS as UI_COLORS  # noqa: F401
from tunacode.constants import URL_DISPLAY_MAX_LENGTH as URL_DISPLAY_MAX_LENGTH  # noqa: F401
from tunacode.constants import build_nextstep_theme as build_nextstep_theme  # noqa: F401
from tunacode.constants import build_tunacode_theme as build_tunacode_theme  # noqa: F401

__all__: list[str] = [
    "APP_NAME",
    "APP_VERSION",
    "BOX_HORIZONTAL",
    "ENV_OPENAI_BASE_URL",
    "HOOK_ARROW_PREFIX",
    "MAX_CALLBACK_CONTENT",
    "MAX_PANEL_LINES",
    "MAX_SEARCH_RESULTS_DISPLAY",
    "MIN_TOOL_PANEL_LINE_WIDTH",
    "MIN_VIEWPORT_LINES",
    "MODEL_PICKER_UNFILTERED_LIMIT",
    "RESOURCE_BAR_COST_FORMAT",
    "RESOURCE_BAR_SEPARATOR",
    "RICHLOG_CLASS_PAUSED",
    "RICHLOG_CLASS_STREAMING",
    "SEPARATOR_WIDTH",
    "SYNTAX_LINE_NUMBER_PADDING",
    "SYNTAX_LINE_NUMBER_SEPARATOR_WIDTH",
    "TOOL_PANEL_HORIZONTAL_INSET",
    "TOOL_PANEL_WIDTH_DEBUG",
    "TOOL_VIEWPORT_LINES",
    "UI_COLORS",
    "URL_DISPLAY_MAX_LENGTH",
    "build_nextstep_theme",
    "build_tunacode_theme",
]
