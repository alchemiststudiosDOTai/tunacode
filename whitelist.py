# Vulture whitelist - properly formatted
# This file tells vulture about false positives

# TYPE_CHECKING imports in src/tunacode/services/mcp.py
from mcp.client.stdio import ReadStream, WriteStream  # noqa: F401

from tunacode.core.state import StateManager  # noqa: F401


# DSPy framework required parameters
def _unused_dspy_params():
    """Reference unused DSPy parameters to satisfy vulture"""
    _trace = None  # Used in lambda functions in dspy_tunacode.py


# Pytest fixtures and common test patterns
def _unused_test_fixtures():
    """Reference common pytest fixtures"""
    # caplog = None  # Common pytest fixture
    # temp_workspace = None  # Common pytest fixture
    # setup_test_environment = None  # Common pytest fixture
    # excinfo = None  # Common pytest fixture
    # kw = None  # Common **kw pattern


# Prompt toolkit completers
def _unused_completer_params():
    """Reference unused completer parameters"""
    _complete_event = None  # Required by prompt_toolkit API


# Other false positives
def _unused_types():
    """Reference other potentially unused items"""
    from tunacode.types import ModelRequest  # noqa: F401

    # kwargs = {}  # Common **kwargs pattern
    # message = None  # Common exception handling pattern
    # response_obj = None  # API response handling
    from tunacode.ui.completers import CommandRegistry  # noqa: F401
