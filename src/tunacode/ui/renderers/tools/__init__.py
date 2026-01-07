"""Tool-specific panel renderers following NeXTSTEP UI principles."""

from tunacode.ui.renderers.tools.base import (
    BOX_HORIZONTAL,
    SEPARATOR_WIDTH,
    BaseToolRenderer,
    RendererConfig,
    RenderFunc,
    ToolRendererProtocol,
    get_renderer,
    list_renderers,
    pad_lines,
    tool_renderer,
    truncate_content,
    truncate_line,
)
from tunacode.ui.renderers.tools.bash import render_bash
from tunacode.ui.renderers.tools.glob import render_glob
from tunacode.ui.renderers.tools.grep import render_grep
from tunacode.ui.renderers.tools.list_dir import render_list_dir
from tunacode.ui.renderers.tools.read_file import render_read_file
from tunacode.ui.renderers.tools.research import render_research_codebase
from tunacode.ui.renderers.tools.update_file import render_update_file
from tunacode.ui.renderers.tools.web_fetch import render_web_fetch

__all__ = [
    # Base classes
    "BaseToolRenderer",
    "BOX_HORIZONTAL",
    "RenderFunc",
    "RendererConfig",
    "SEPARATOR_WIDTH",
    "ToolRendererProtocol",
    # Helper functions
    "pad_lines",
    "truncate_content",
    "truncate_line",
    # Registry functions
    "get_renderer",
    "list_renderers",
    "tool_renderer",
    # Render functions
    "render_bash",
    "render_glob",
    "render_grep",
    "render_list_dir",
    "render_read_file",
    "render_research_codebase",
    "render_update_file",
    "render_web_fetch",
]
