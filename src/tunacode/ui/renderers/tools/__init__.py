"""Tool-specific panel renderers following NeXTSTEP UI principles.

All renderers implement a 4-zone layout with syntax highlighting:
- Zone 1: Header (tool name, key stats)
- Zone 2: Params (key-value parameter display)
- Zone 3: Viewport (main content with syntax highlighting)
- Zone 4: Status (truncation info, timing)

Importing this package registers every renderer with the dispatch
registry; look up renderers via get_renderer(tool_name).
"""

from tunacode.ui.renderers.tools.base import get_renderer  # noqa: F401

# Imported for their registration side effect (@tool_renderer decorator).
from tunacode.ui.renderers.tools.bash import render_bash  # noqa: F401
from tunacode.ui.renderers.tools.discover import render_discover  # noqa: F401
from tunacode.ui.renderers.tools.hashline_edit import render_hashline_edit  # noqa: F401
from tunacode.ui.renderers.tools.read_file import render_read_file  # noqa: F401
from tunacode.ui.renderers.tools.web_fetch import render_web_fetch  # noqa: F401
from tunacode.ui.renderers.tools.write_file import render_write_file  # noqa: F401
