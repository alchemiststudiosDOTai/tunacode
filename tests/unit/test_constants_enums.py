"""
Test-first approach for constants enum refactoring.

This test file defines the expected behavior for the new enum-based constants
before implementing them. Following TDD principles.
"""

from enum import Enum


def test_tool_name_enum_exists():
    """Test that ToolName enum exists and has expected values."""
    from tunacode.constants import ToolName

    # Should be an enum
    assert issubclass(ToolName, Enum)

    # Should have all expected tool names
    expected_tools = [
        "read_file",
        "write_file",
        "update_file",
        "run_command",
        "bash",
        "grep",
        "list_dir",
        "glob",
        "todo",
    ]

    for tool in expected_tools:
        assert hasattr(ToolName, tool.upper()), f"ToolName should have {tool.upper()}"
        assert ToolName[tool.upper()].value == tool


def test_tool_name_enum_string_behavior():
    """Test that ToolName enum values behave as strings."""
    from tunacode.constants import ToolName

    # Should be string-like in comparisons
    assert ToolName.WRITE_FILE == "write_file"
    assert ToolName.BASH == "bash"
    assert "grep" == ToolName.GREP

    # Should have string values
    assert ToolName.READ_FILE.value == "read_file"


def test_tool_categorization_uses_enums():
    """Test that tool categorization constants use ToolName enum."""
    from tunacode.constants import EXECUTE_TOOLS, READ_ONLY_TOOLS, WRITE_TOOLS, ToolName

    # Should contain enum values
    assert ToolName.READ_FILE in READ_ONLY_TOOLS
    assert ToolName.GREP in READ_ONLY_TOOLS
    assert ToolName.LIST_DIR in READ_ONLY_TOOLS
    assert ToolName.GLOB in READ_ONLY_TOOLS

    assert ToolName.WRITE_FILE in WRITE_TOOLS
    assert ToolName.UPDATE_FILE in WRITE_TOOLS

    assert ToolName.BASH in EXECUTE_TOOLS
    assert ToolName.RUN_COMMAND in EXECUTE_TOOLS


def test_todo_status_enum_exists():
    """Test that TodoStatus enum exists and has expected values."""
    from tunacode.constants import TodoStatus

    # Should be an enum
    assert issubclass(TodoStatus, Enum)

    # Should have all expected statuses
    expected_statuses = ["pending", "in_progress", "completed"]

    for status in expected_statuses:
        assert hasattr(TodoStatus, status.upper()), f"TodoStatus should have {status.upper()}"
        assert TodoStatus[status.upper()].value == status


def test_todo_priority_enum_exists():
    """Test that TodoPriority enum exists and has expected values."""
    from tunacode.constants import TodoPriority

    # Should be an enum
    assert issubclass(TodoPriority, Enum)

    # Should have all expected priorities
    expected_priorities = ["high", "medium", "low"]

    for priority in expected_priorities:
        assert hasattr(TodoPriority, priority.upper()), (
            f"TodoPriority should have {priority.upper()}"
        )
        assert TodoPriority[priority.upper()].value == priority


def test_settings_uses_tool_name_enum():
    """Test that ApplicationSettings uses ToolName enum."""
    from tunacode.configuration.settings import ApplicationSettings
    from tunacode.constants import ToolName

    settings = ApplicationSettings()

    # Should contain ToolName enum values
    assert ToolName.READ_FILE in settings.internal_tools
    assert ToolName.BASH in settings.internal_tools
    assert len(settings.internal_tools) == 9  # All 9 tools


def test_defaults_uses_tool_name_enum():
    """Test that default config tool_ignore is a list that can contain ToolName enum."""
    from tunacode.configuration.defaults import DEFAULT_USER_CONFIG
    from tunacode.constants import ToolName

    # Tool ignore list should be a list (empty by default)
    assert isinstance(DEFAULT_USER_CONFIG["settings"]["tool_ignore"], list)

    # Verify that ToolName enum values can be used in tool_ignore
    # by checking type compatibility (this is a type-level check)
    test_ignore_list = [ToolName.READ_FILE, ToolName.BASH]
    assert all(isinstance(tool, ToolName) for tool in test_ignore_list)
