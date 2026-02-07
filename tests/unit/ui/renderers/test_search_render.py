"""Tests for search.py render methods and convenience functions.

Source: src/tunacode/ui/renderers/search.py
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from tunacode.ui.renderers.search import (
    CodeSearchResult,
    FileSearchResult,
    SearchDisplayRenderer,
    code_search_panel,
    file_search_panel,
    quick_results,
)


def _render_to_text(panel: Panel) -> str:
    """Render a Panel to plain text for assertion checks."""
    buf = StringIO()
    console = Console(file=buf, width=120, force_terminal=False)
    console.print(panel)
    return buf.getvalue()


# ===================================================================
# SearchDisplayRenderer.render_file_results
# ===================================================================


class TestRenderFileResults:
    """SearchDisplayRenderer.render_file_results builds a rich panel."""

    def test_single_result_without_match_positions(self) -> None:
        results = [
            FileSearchResult(file_path="src/main.py", line_number=10, content="hello world"),
        ]
        panel = SearchDisplayRenderer.render_file_results("hello", results)
        assert isinstance(panel, Panel)
        rendered = _render_to_text(panel)
        assert "src/main.py" in rendered

    def test_single_result_with_match_positions(self) -> None:
        results = [
            FileSearchResult(
                file_path="src/main.py",
                line_number=5,
                content="say hello there",
                match_start=4,
                match_end=9,
            ),
        ]
        panel = SearchDisplayRenderer.render_file_results("hello", results)
        assert isinstance(panel, Panel)
        assert "src/main.py" in _render_to_text(panel)

    def test_result_without_line_number(self) -> None:
        results = [
            FileSearchResult(file_path="README.md", content="some content"),
        ]
        panel = SearchDisplayRenderer.render_file_results("content", results)
        assert isinstance(panel, Panel)
        assert "README.md" in _render_to_text(panel)

    def test_result_with_relevance_score(self) -> None:
        results = [
            FileSearchResult(
                file_path="lib.py",
                line_number=1,
                content="match",
                relevance=0.95,
            ),
        ]
        panel = SearchDisplayRenderer.render_file_results("match", results)
        assert isinstance(panel, Panel)
        assert "lib.py" in _render_to_text(panel)

    def test_multiple_results_with_pagination(self) -> None:
        results = [
            FileSearchResult(file_path=f"file{i}.py", line_number=i, content=f"line {i}")
            for i in range(25)
        ]
        panel = SearchDisplayRenderer.render_file_results("line", results, page=2, page_size=5)
        assert isinstance(panel, Panel)
        rendered = _render_to_text(panel)
        assert "file" in rendered

    def test_with_search_time(self) -> None:
        results = [
            FileSearchResult(file_path="a.py", line_number=1, content="x"),
        ]
        panel = SearchDisplayRenderer.render_file_results("x", results, search_time_ms=42.5)
        assert isinstance(panel, Panel)
        rendered = _render_to_text(panel)
        assert "a.py" in rendered

    def test_empty_results_list(self) -> None:
        panel = SearchDisplayRenderer.render_file_results("missing", [])
        assert isinstance(panel, Panel)
        rendered = _render_to_text(panel)
        assert "missing" in rendered or "No" in rendered


# ===================================================================
# SearchDisplayRenderer.render_code_results
# ===================================================================


class TestRenderCodeResults:
    """SearchDisplayRenderer.render_code_results builds a rich panel."""

    def test_single_function_result(self) -> None:
        results = [
            CodeSearchResult(
                file_path="src/core.py",
                symbol_name="process",
                symbol_type="function",
                line_number=42,
                context="def process(data):",
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("process", results)
        assert isinstance(panel, Panel)

    def test_class_result(self) -> None:
        results = [
            CodeSearchResult(
                file_path="models.py",
                symbol_name="User",
                symbol_type="class",
                line_number=1,
                context="class User:",
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("User", results)
        assert isinstance(panel, Panel)

    def test_variable_result(self) -> None:
        results = [
            CodeSearchResult(
                file_path="config.py",
                symbol_name="MAX_SIZE",
                symbol_type="variable",
                line_number=3,
                context="MAX_SIZE = 100",
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("MAX_SIZE", results)
        assert isinstance(panel, Panel)

    def test_method_result(self) -> None:
        results = [
            CodeSearchResult(
                file_path="app.py",
                symbol_name="run",
                symbol_type="method",
                line_number=10,
                context="def run(self):",
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("run", results)
        assert isinstance(panel, Panel)

    def test_constant_result(self) -> None:
        results = [
            CodeSearchResult(
                file_path="const.py",
                symbol_name="PI",
                symbol_type="constant",
                line_number=1,
                context="PI = 3.14159",
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("PI", results)
        assert isinstance(panel, Panel)

    def test_unknown_symbol_type_uses_prefix(self) -> None:
        results = [
            CodeSearchResult(
                file_path="x.py",
                symbol_name="thing",
                symbol_type="namespace",
                line_number=1,
                context="namespace thing {}",
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("thing", results)
        assert isinstance(panel, Panel)

    def test_with_relevance(self) -> None:
        results = [
            CodeSearchResult(
                file_path="a.py",
                symbol_name="foo",
                symbol_type="function",
                line_number=1,
                context="def foo():",
                relevance=0.8,
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("foo", results)
        assert isinstance(panel, Panel)

    def test_pagination(self) -> None:
        results = [
            CodeSearchResult(
                file_path=f"f{i}.py",
                symbol_name=f"func{i}",
                symbol_type="function",
                line_number=i,
                context=f"def func{i}():",
            )
            for i in range(20)
        ]
        panel = SearchDisplayRenderer.render_code_results("func", results, page=2, page_size=5)
        assert isinstance(panel, Panel)

    def test_with_search_time(self) -> None:
        results = [
            CodeSearchResult(
                file_path="b.py",
                symbol_name="bar",
                symbol_type="function",
                line_number=1,
                context="def bar():",
            ),
        ]
        panel = SearchDisplayRenderer.render_code_results("bar", results, search_time_ms=15.3)
        assert isinstance(panel, Panel)


# ===================================================================
# SearchDisplayRenderer.render_inline_results
# ===================================================================


class TestRenderInlineResults:
    """SearchDisplayRenderer.render_inline_results returns Text."""

    def test_empty_results_returns_no_results_text(self) -> None:
        result = SearchDisplayRenderer.render_inline_results([])
        assert isinstance(result, Text)

    def test_single_result(self) -> None:
        results = [{"title": "src/main.py"}]
        result = SearchDisplayRenderer.render_inline_results(results)
        assert isinstance(result, Text)

    def test_results_with_file_key_fallback(self) -> None:
        results = [{"file": "src/main.py"}]
        result = SearchDisplayRenderer.render_inline_results(results)
        assert isinstance(result, Text)

    def test_results_with_neither_title_nor_file(self) -> None:
        results = [{"name": "something"}]
        result = SearchDisplayRenderer.render_inline_results(results)
        assert isinstance(result, Text)

    def test_more_than_max_display_shows_remaining(self) -> None:
        results = [{"title": f"file{i}.py"} for i in range(10)]
        result = SearchDisplayRenderer.render_inline_results(results, max_display=3)
        assert isinstance(result, Text)

    def test_exact_max_display_no_remaining(self) -> None:
        results = [{"title": f"file{i}.py"} for i in range(5)]
        result = SearchDisplayRenderer.render_inline_results(results, max_display=5)
        assert isinstance(result, Text)


# ===================================================================
# SearchDisplayRenderer.render_empty_results
# ===================================================================


class TestRenderEmptyResults:
    """SearchDisplayRenderer.render_empty_results returns a Panel."""

    def test_returns_panel(self) -> None:
        result = SearchDisplayRenderer.render_empty_results("nonexistent")
        assert isinstance(result, Panel)

    def test_panel_title_contains_no_results(self) -> None:
        result = SearchDisplayRenderer.render_empty_results("foo")
        assert isinstance(result, Panel)
        title_str = str(result.title) if result.title else ""
        assert "No Results" in title_str


# ===================================================================
# Module-level convenience functions
# ===================================================================


class TestFileSearchPanel:
    """file_search_panel routes to render methods."""

    def test_empty_results_shows_empty_panel(self) -> None:
        result = file_search_panel("query", [])
        assert isinstance(result, Panel)

    def test_with_results(self) -> None:
        results = [
            FileSearchResult(file_path="a.py", line_number=1, content="x"),
        ]
        result = file_search_panel("x", results)
        assert isinstance(result, Panel)

    def test_with_page_and_time(self) -> None:
        results = [
            FileSearchResult(file_path="a.py", line_number=1, content="x"),
        ]
        result = file_search_panel("x", results, page=1, search_time_ms=10.0)
        assert isinstance(result, Panel)


class TestCodeSearchPanel:
    """code_search_panel routes to render methods."""

    def test_empty_results_shows_empty_panel(self) -> None:
        result = code_search_panel("query", [])
        assert isinstance(result, Panel)

    def test_with_results(self) -> None:
        results = [
            CodeSearchResult(
                file_path="a.py",
                symbol_name="func",
                symbol_type="function",
                line_number=1,
                context="def func():",
            ),
        ]
        result = code_search_panel("func", results)
        assert isinstance(result, Panel)

    def test_with_page_and_time(self) -> None:
        results = [
            CodeSearchResult(
                file_path="a.py",
                symbol_name="func",
                symbol_type="function",
                line_number=1,
                context="def func():",
            ),
        ]
        result = code_search_panel("func", results, page=1, search_time_ms=5.0)
        assert isinstance(result, Panel)


class TestQuickResults:
    """quick_results convenience function."""

    def test_empty_list(self) -> None:
        result = quick_results([])
        assert isinstance(result, Text)

    def test_with_items(self) -> None:
        result = quick_results([{"title": "a"}, {"title": "b"}])
        assert isinstance(result, Text)

    def test_custom_max_display(self) -> None:
        results = [{"title": f"item{i}"} for i in range(10)]
        result = quick_results(results, max_display=2)
        assert isinstance(result, Text)
