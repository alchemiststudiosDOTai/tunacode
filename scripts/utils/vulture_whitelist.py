# Vulture whitelist for false positives
# This file is used by vulture to ignore certain false positives that are actually used in the code
#
# How vulture whitelists work:
# - Vulture scans this file and considers any symbol defined here as "used"
# - For function parameters, we define dummy functions that "use" them
# - For imports, we import and reference them

from typing import Any

# TYPE_CHECKING imports in src/tunacode/core/state.py
ToolHandler = None  # noqa: F841

# TYPE_CHECKING imports used in string annotations
# These imports are used in quoted type annotations like "StreamedRunResult[None, str]"
# but vulture can't detect usage inside strings
from pydantic_ai.result import StreamedRunResult  # noqa: F401
from pydantic_ai.messages import ToolCallPart  # noqa: F401

_ = StreamedRunResult  # Mark as used
_ = ToolCallPart  # Mark as used


# Protocol/Abstract method parameters - these define interfaces, not unused code
# Vulture can't understand that Protocol method params ARE the interface
def _whitelist_protocol_params(
    context: dict[str, Any],  # state.py, base.py
    session_id: str,  # state.py StateManagerProtocol.load_session()
    renderable: Any,  # shell_runner.py, welcome.py Protocol methods
    response: Any,  # main.py - may be used for type narrowing
) -> None:
    """Dummy function to whitelist Protocol method parameters."""
    _ = context
    _ = session_id
    _ = renderable
    _ = response
