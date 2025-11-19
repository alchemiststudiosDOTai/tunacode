"""Tests for agent_helpers module."""

from tunacode.core.agents.agent_components.agent_helpers import (
    get_readable_tool_description,
)


class TestGetReadableToolDescription:
    """Test the get_readable_tool_description function."""

    def test_read_file_with_path(self):
        """Test read_file tool description."""
        result = get_readable_tool_description("read_file", {"file_path": "src/main.py"})
        assert result == "Reading `src/main.py`"

    def test_list_dir_with_directory(self):
        """Test list_dir tool description."""
        result = get_readable_tool_description("list_dir", {"directory": "tests/"})
        assert result == "Listing directory `tests/`"

    def test_grep_with_pattern_and_files(self):
        """Test grep tool description with pattern and files."""
        result = get_readable_tool_description(
            "grep", {"pattern": "def foo", "include_files": "*.py"}
        )
        assert result == "Searching for `def foo` in `*.py`"

    def test_grep_with_pattern_only(self):
        """Test grep tool description with pattern only."""
        result = get_readable_tool_description("grep", {"pattern": "class Bar"})
        assert result == "Searching for `class Bar`"

    def test_glob_with_pattern(self):
        """Test glob tool description."""
        result = get_readable_tool_description("glob", {"pattern": "**/*.ts"})
        assert result == "Finding files matching `**/*.ts`"

    def test_research_codebase_with_query(self):
        """Test research_codebase tool description."""
        result = get_readable_tool_description(
            "research_codebase", {"query": "How does authentication work?"}
        )
        assert result == "Researching: How does authentication work?"

    def test_research_codebase_long_query(self):
        """Test research_codebase with long query truncation."""
        long_query = (
            "How does the authentication system work with JWT tokens "
            "and refresh tokens in the backend?"
        )
        result = get_readable_tool_description("research_codebase", {"query": long_query})
        # Should be truncated to 60 chars + "..."
        assert len(result) <= len("Researching: ") + 63
        assert result.endswith("...")

    def test_unknown_tool(self):
        """Test fallback for unknown tool."""
        result = get_readable_tool_description("unknown_tool", {})
        assert result == "Executing `unknown_tool`"

    def test_tool_without_args(self):
        """Test tool with non-dict args."""
        result = get_readable_tool_description("some_tool", "not_a_dict")
        assert result == "Executing `some_tool`"

    def test_read_file_without_path(self):
        """Test read_file without file_path."""
        result = get_readable_tool_description("read_file", {})
        assert result == "Reading file"

    def test_list_dir_without_directory(self):
        """Test list_dir without directory."""
        result = get_readable_tool_description("list_dir", {})
        assert result == "Listing directory"

    def test_grep_without_pattern(self):
        """Test grep without pattern."""
        result = get_readable_tool_description("grep", {})
        assert result == "Searching files"

    def test_glob_without_pattern(self):
        """Test glob without pattern."""
        result = get_readable_tool_description("glob", {})
        assert result == "Finding files"

    def test_research_codebase_without_query(self):
        """Test research_codebase without query."""
        result = get_readable_tool_description("research_codebase", {})
        assert result == "Researching codebase"
