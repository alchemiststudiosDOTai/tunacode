"""Rich content renderers for Textual TUI."""

from __future__ import annotations

import importlib
from typing import Any

_RENDERER_EXPORTS = {
    "render_exception": ".errors",
    "ErrorDisplayData": ".panels",
    "RichPanelRenderer": ".panels",
    "SearchResultData": ".panels",
    "ToolDisplayData": ".panels",
    "error_panel": ".panels",
    "search_panel": ".panels",
    "tool_panel": ".panels",
    "tool_panel_smart": ".panels",
    "CodeSearchResult": ".search",
    "FileSearchResult": ".search",
    "SearchDisplayRenderer": ".search",
}


def __getattr__(name: str) -> Any:
    module_name = _RENDERER_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module_name, __name__), name)
