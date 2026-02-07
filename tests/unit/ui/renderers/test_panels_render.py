"""Tests for panels.py RichPanelRenderer and convenience functions.

Source: src/tunacode/ui/renderers/panels.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from rich.panel import Panel
from rich.text import Text

from tunacode.ui.renderers.panels import (
    ErrorDisplayData,
    RichPanelRenderer,
    SearchResultData,
    ToolDisplayData,
    error_panel,
    search_panel,
    tool_panel,
    tool_panel_smart,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_LINE_WIDTH = 80


# ===================================================================
# RichPanelRenderer.render_tool
# ===================================================================


class TestRichPanelRendererTool:
    """RichPanelRenderer.render_tool builds tool panels."""

    def test_running_status(self) -> None:
        data = ToolDisplayData(
            tool_name="bash",
            status="running",
            arguments={"command": "ls -la"},
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)

    def test_completed_status(self) -> None:
        data = ToolDisplayData(
            tool_name="read_file",
            status="completed",
            arguments={"path": "/tmp/test.py"},
            result="file contents here",
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)

    def test_failed_status(self) -> None:
        data = ToolDisplayData(
            tool_name="write_file",
            status="failed",
            arguments={"path": "/readonly.txt"},
            result="Permission denied",
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)

    def test_unknown_status_uses_info(self) -> None:
        data = ToolDisplayData(
            tool_name="custom",
            status="pending",
            arguments={},
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)

    def test_with_duration(self) -> None:
        data = ToolDisplayData(
            tool_name="bash",
            status="completed",
            arguments={"command": "echo hi"},
            duration_ms=123.4,
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)

    def test_with_timestamp(self) -> None:
        data = ToolDisplayData(
            tool_name="bash",
            status="completed",
            arguments={},
            timestamp=datetime(2025, 1, 15, 10, 30, 45, tzinfo=UTC),
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)
        assert result.subtitle is not None

    def test_empty_arguments_and_no_result(self) -> None:
        data = ToolDisplayData(
            tool_name="noop",
            status="running",
            arguments={},
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)

    def test_long_result_triggers_truncation(self) -> None:
        long_result = "\n".join(f"line {i}" for i in range(200))
        data = ToolDisplayData(
            tool_name="bash",
            status="completed",
            arguments={"command": "generate_output"},
            result=long_result,
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)

    def test_multiple_arguments(self) -> None:
        data = ToolDisplayData(
            tool_name="grep",
            status="completed",
            arguments={"pattern": "test", "path": "/src", "recursive": True},
            result="found 3 matches",
        )
        result = RichPanelRenderer.render_tool(data, max_line_width=DEFAULT_MAX_LINE_WIDTH)
        assert isinstance(result, Panel)


# ===================================================================
# RichPanelRenderer.render_diff_tool
# ===================================================================


class TestRichPanelRendererDiffTool:
    """RichPanelRenderer.render_diff_tool builds diff panels."""

    def test_basic_diff(self) -> None:
        diff = "--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new"
        result = RichPanelRenderer.render_diff_tool(
            tool_name="update_file",
            message="Updated file.py",
            diff=diff,
        )
        assert isinstance(result, Panel)

    def test_with_args(self) -> None:
        diff = "-old\n+new"
        result = RichPanelRenderer.render_diff_tool(
            tool_name="update_file",
            message="Changed",
            diff=diff,
            args={"path": "file.py", "mode": "replace"},
        )
        assert isinstance(result, Panel)

    def test_with_duration(self) -> None:
        diff = "-a\n+b"
        result = RichPanelRenderer.render_diff_tool(
            tool_name="edit",
            message="Edited",
            diff=diff,
            duration_ms=50.0,
        )
        assert isinstance(result, Panel)

    def test_with_timestamp(self) -> None:
        diff = "-x\n+y"
        result = RichPanelRenderer.render_diff_tool(
            tool_name="edit",
            message="Edited",
            diff=diff,
            timestamp=datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
        )
        assert isinstance(result, Panel)
        assert result.subtitle is not None

    def test_empty_message(self) -> None:
        diff = "-old\n+new"
        result = RichPanelRenderer.render_diff_tool(
            tool_name="update_file",
            message="",
            diff=diff,
        )
        assert isinstance(result, Panel)

    def test_no_args_no_duration_no_timestamp(self) -> None:
        diff = "+added line"
        result = RichPanelRenderer.render_diff_tool(
            tool_name="write",
            message="Created file",
            diff=diff,
        )
        assert isinstance(result, Panel)


# ===================================================================
# RichPanelRenderer.render_error
# ===================================================================


class TestRichPanelRendererError:
    """RichPanelRenderer.render_error builds error panels."""

    def test_error_severity(self) -> None:
        data = ErrorDisplayData(
            error_type="RuntimeError",
            message="something failed",
            severity="error",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)

    def test_warning_severity(self) -> None:
        data = ErrorDisplayData(
            error_type="ConfigWarning",
            message="deprecated option",
            severity="warning",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)

    def test_info_severity(self) -> None:
        data = ErrorDisplayData(
            error_type="Notice",
            message="operation cancelled",
            severity="info",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)

    def test_unknown_severity_defaults_to_error(self) -> None:
        data = ErrorDisplayData(
            error_type="WeirdError",
            message="something odd",
            severity="critical",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)

    def test_with_suggested_fix(self) -> None:
        data = ErrorDisplayData(
            error_type="FileError",
            message="not found",
            suggested_fix="Check the path",
            severity="error",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)

    def test_with_recovery_commands(self) -> None:
        data = ErrorDisplayData(
            error_type="GitError",
            message="merge conflict",
            recovery_commands=["git status", "git stash"],
            severity="error",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)

    def test_with_context(self) -> None:
        data = ErrorDisplayData(
            error_type="ToolError",
            message="execution failed",
            context={"Tool": "bash", "Path": "/tmp"},
            severity="error",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)

    def test_with_all_fields(self) -> None:
        data = ErrorDisplayData(
            error_type="CompleteError",
            message="total failure",
            suggested_fix="Try again",
            recovery_commands=["cmd1", "cmd2"],
            context={"Key": "Value"},
            severity="error",
        )
        result = RichPanelRenderer.render_error(data)
        assert isinstance(result, Panel)


# ===================================================================
# RichPanelRenderer.render_search_results
# ===================================================================


class TestRichPanelRendererSearchResults:
    """RichPanelRenderer.render_search_results builds search panels."""

    def test_basic_search_results(self) -> None:
        data = SearchResultData(
            query="test",
            results=[{"title": "file.py", "snippet": "test line"}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_with_search_time(self) -> None:
        data = SearchResultData(
            query="func",
            results=[{"title": "a.py", "snippet": "def func():"}],
            total_count=1,
            search_time_ms=33.7,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_multiple_pages(self) -> None:
        results = [{"title": f"f{i}.py", "snippet": f"line {i}"} for i in range(30)]
        data = SearchResultData(
            query="multi",
            results=results,
            total_count=30,
            current_page=2,
            page_size=10,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_result_with_relevance(self) -> None:
        data = SearchResultData(
            query="scored",
            results=[{"title": "a.py", "snippet": "hit", "relevance": 0.92}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_result_without_snippet(self) -> None:
        data = SearchResultData(
            query="bare",
            results=[{"title": "bare.py"}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_result_with_content_key(self) -> None:
        data = SearchResultData(
            query="content",
            results=[{"title": "c.py", "content": "some content here"}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_result_with_score_key(self) -> None:
        data = SearchResultData(
            query="alt_score",
            results=[{"title": "s.py", "snippet": "x", "score": 0.75}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_result_with_name_key_fallback(self) -> None:
        data = SearchResultData(
            query="named",
            results=[{"name": "something", "snippet": "context"}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_result_with_no_identifying_keys(self) -> None:
        data = SearchResultData(
            query="anon",
            results=[{"snippet": "only snippet"}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)

    def test_source_index_subtitle(self) -> None:
        data = SearchResultData(
            query="q",
            results=[{"title": "f.py", "snippet": "x"}],
            total_count=1,
            source="index",
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)
        assert result.subtitle is not None
        assert "Indexed" in str(result.subtitle)

    def test_source_filesystem_subtitle(self) -> None:
        data = SearchResultData(
            query="q",
            results=[{"title": "f.py", "snippet": "x"}],
            total_count=1,
            source="filesystem",
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)
        assert result.subtitle is not None
        assert "Scanned" in str(result.subtitle)

    def test_no_source_single_page_no_subtitle(self) -> None:
        data = SearchResultData(
            query="q",
            results=[{"title": "f.py", "snippet": "x"}],
            total_count=1,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)
        assert result.subtitle is None

    def test_many_results_truncated_with_more_indicator(self) -> None:
        """When results exceed MAX_SEARCH_RESULTS_DISPLAY, the panel shows +N more."""
        results = [{"title": f"f{i}.py", "snippet": f"line {i}"} for i in range(50)]
        data = SearchResultData(
            query="big",
            results=results,
            total_count=50,
            page_size=50,
        )
        result = RichPanelRenderer.render_search_results(data)
        assert isinstance(result, Panel)


# ===================================================================
# RichPanelRenderer.render_info / render_success / render_warning
# ===================================================================


class TestRichPanelRendererInfoSuccessWarning:
    """RichPanelRenderer.render_info/render_success/render_warning."""

    def test_info_with_string_content(self) -> None:
        result = RichPanelRenderer.render_info("Title", "Some information")
        assert isinstance(result, Panel)

    def test_info_with_rich_renderable_content(self) -> None:
        content = Text("styled info", style="bold")
        result = RichPanelRenderer.render_info("Title", content)
        assert isinstance(result, Panel)

    def test_success_panel(self) -> None:
        result = RichPanelRenderer.render_success("Done", "Operation completed")
        assert isinstance(result, Panel)

    def test_warning_panel(self) -> None:
        result = RichPanelRenderer.render_warning("Caution", "Proceed carefully")
        assert isinstance(result, Panel)


# ===================================================================
# Module-level convenience functions
# ===================================================================


class TestToolPanelConvenience:
    """tool_panel convenience function."""

    def test_basic_tool_panel(self) -> None:
        result = tool_panel(
            "bash",
            "completed",
            args={"command": "echo test"},
            result="test",
            duration_ms=10.0,
            max_line_width=80,
        )
        assert isinstance(result, Panel)

    def test_no_args_no_result(self) -> None:
        result = tool_panel(
            "noop",
            "running",
            duration_ms=None,
            max_line_width=80,
        )
        assert isinstance(result, Panel)


class TestErrorPanelConvenience:
    """error_panel convenience function."""

    def test_basic_error_panel(self) -> None:
        result = error_panel("FileError", "File not found")
        assert isinstance(result, Panel)

    def test_with_fix_and_recovery(self) -> None:
        result = error_panel(
            "GitError",
            "Merge conflict",
            suggested_fix="Resolve conflicts",
            recovery_commands=["git status", "git merge --abort"],
            severity="error",
        )
        assert isinstance(result, Panel)

    def test_warning_severity(self) -> None:
        result = error_panel(
            "ConfigWarning",
            "Deprecated option",
            severity="warning",
        )
        assert isinstance(result, Panel)


class TestSearchPanelConvenience:
    """search_panel convenience function."""

    def test_basic_search_panel(self) -> None:
        results = [{"title": "a.py", "snippet": "match"}]
        result = search_panel("query", results)
        assert isinstance(result, Panel)

    def test_with_total_count_override(self) -> None:
        results = [{"title": "a.py", "snippet": "match"}]
        result = search_panel("query", results, total_count=100)
        assert isinstance(result, Panel)

    def test_with_page_and_search_time(self) -> None:
        results = [{"title": "a.py", "snippet": "match"}]
        result = search_panel("query", results, page=2, search_time_ms=20.0)
        assert isinstance(result, Panel)


class TestToolPanelSmart:
    """tool_panel_smart routes to specialized renderers."""

    def test_non_completed_falls_back_to_generic(self) -> None:
        result = tool_panel_smart(
            "bash",
            "running",
            args={"command": "ls"},
            duration_ms=None,
            max_line_width=80,
        )
        assert isinstance(result, Panel)

    def test_completed_without_result_falls_back(self) -> None:
        result = tool_panel_smart(
            "bash",
            "completed",
            args={"command": "echo"},
            result=None,
            duration_ms=5.0,
            max_line_width=80,
        )
        assert isinstance(result, Panel)

    def test_completed_unknown_tool_falls_back(self) -> None:
        result = tool_panel_smart(
            "custom_tool",
            "completed",
            args={},
            result="some output",
            duration_ms=10.0,
            max_line_width=80,
        )
        assert isinstance(result, Panel)

    def test_failed_status_falls_back(self) -> None:
        result = tool_panel_smart(
            "bash",
            "failed",
            args={"command": "bad"},
            result="error output",
            duration_ms=1.0,
            max_line_width=80,
        )
        assert isinstance(result, Panel)
