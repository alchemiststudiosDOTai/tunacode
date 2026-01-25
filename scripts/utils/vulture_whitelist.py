# Vulture whitelist for false positives
# This file is used by vulture to ignore certain false positives that are actually used in the code

# These are used but vulture can't detect them properly

# TYPE_CHECKING imports in src/tunacode/core/state.py
ToolHandler = None  # noqa: F841

# Abstract method parameter in src/tunacode/cli/commands/base.py
context = None  # noqa: F841

# TYPE_CHECKING imports used in string annotations
# These imports are used in quoted type annotations like "StreamedRunResult[None, str]"
# but vulture can't detect usage inside strings
from pydantic_ai.result import StreamedRunResult  # noqa: F401
from pydantic_ai.messages import ToolCallPart  # noqa: F401

_ = StreamedRunResult  # Mark as used
_ = ToolCallPart  # Mark as used
