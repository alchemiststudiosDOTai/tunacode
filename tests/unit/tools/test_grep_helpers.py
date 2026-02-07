"""Tests for grep helper functions in tunacode.tools.grep."""

from tunacode.tools.grep import (
    SMART_PYTHON_THRESHOLD,
    SMART_RIPGREP_THRESHOLD,
    _flatten_search_results,
    _format_search_output,
    _select_search_strategy,
)
from tunacode.tools.grep_components import SearchConfig, SearchResult
from tunacode.tools.grep_components.result_formatter import ResultFormatter


class TestSelectSearchStrategy:
    def test_non_smart_returns_as_is(self):
        assert _select_search_strategy("ripgrep", 10) == "ripgrep"
        assert _select_search_strategy("python", 100) == "python"
        assert _select_search_strategy("hybrid", 5000) == "hybrid"

    def test_smart_small_count_returns_python(self):
        assert _select_search_strategy("smart", 10) == "python"
        assert _select_search_strategy("smart", SMART_PYTHON_THRESHOLD) == "python"

    def test_smart_medium_count_returns_ripgrep(self):
        assert _select_search_strategy("smart", SMART_PYTHON_THRESHOLD + 1) == "ripgrep"
        assert _select_search_strategy("smart", SMART_RIPGREP_THRESHOLD) == "ripgrep"

    def test_smart_large_count_returns_hybrid(self):
        assert _select_search_strategy("smart", SMART_RIPGREP_THRESHOLD + 1) == "hybrid"
        assert _select_search_strategy("smart", 10000) == "hybrid"

    def test_smart_zero_returns_python(self):
        assert _select_search_strategy("smart", 0) == "python"


def _make_result(file_path: str, score: float) -> SearchResult:
    return SearchResult(
        file_path=file_path,
        line_number=1,
        line_content="content",
        match_start=0,
        match_end=7,
        context_before=[],
        context_after=[],
        relevance_score=score,
    )


class TestFlattenSearchResults:
    def test_flattens_nested_lists(self):
        batch1 = [_make_result("a.py", 1.0)]
        batch2 = [_make_result("b.py", 0.5)]
        result = _flatten_search_results([batch1, batch2], max_results=10)
        assert len(result) == 2

    def test_filters_exceptions(self):
        batch = [_make_result("a.py", 1.0)]
        result = _flatten_search_results([batch, ValueError("oops")], max_results=10)
        assert len(result) == 1

    def test_sorts_by_relevance_descending(self):
        batch = [_make_result("low.py", 0.1), _make_result("high.py", 0.9)]
        result = _flatten_search_results([batch], max_results=10)
        assert result[0].file_path == "high.py"
        assert result[1].file_path == "low.py"

    def test_respects_max_results(self):
        batch = [_make_result(f"f{i}.py", float(i)) for i in range(20)]
        result = _flatten_search_results([batch], max_results=5)
        assert len(result) == 5
        # Top-scored items should be retained (descending order)
        top_files = [r.file_path for r in result]
        assert top_files == [f"f{i}.py" for i in range(19, 14, -1)]

    def test_empty_input(self):
        assert _flatten_search_results([], max_results=10) == []

    def test_all_exceptions(self):
        result = _flatten_search_results([ValueError("a"), RuntimeError("b")], max_results=10)
        assert result == []


class TestFormatSearchOutput:
    def test_list_format_returns_unique_paths(self):
        results = [
            _make_result("a.py", 1.0),
            _make_result("a.py", 0.9),
            _make_result("b.py", 0.8),
        ]
        config = SearchConfig(
            case_sensitive=False,
            use_regex=False,
            max_results=50,
            context_lines=2,
        )
        formatter = ResultFormatter()
        output = _format_search_output(
            results=results,
            pattern="test",
            config=config,
            output_mode="content",
            search_type="python",
            original_search_type="smart",
            candidate_count=10,
            return_format="list",
            formatter=formatter,
        )
        assert isinstance(output, list)
        assert set(output) == {"a.py", "b.py"}

    def test_string_format_returns_str(self):
        results = [_make_result("a.py", 1.0)]
        config = SearchConfig(
            case_sensitive=False,
            use_regex=False,
            max_results=50,
            context_lines=2,
        )
        formatter = ResultFormatter()
        output = _format_search_output(
            results=results,
            pattern="test",
            config=config,
            output_mode="content",
            search_type="python",
            original_search_type="smart",
            candidate_count=10,
            return_format="string",
            formatter=formatter,
        )
        assert isinstance(output, str)
        # When output starts with "Found", the second line has injected strategy metadata
        lines = output.split("\n")
        assert output.startswith("Found")
        assert "Strategy:" in lines[1]

    def test_string_format_non_found_branch(self):
        config = SearchConfig(
            case_sensitive=False,
            use_regex=False,
            max_results=50,
            context_lines=2,
        )
        formatter = ResultFormatter()
        output = _format_search_output(
            results=[],
            pattern="nonexistent",
            config=config,
            output_mode="content",
            search_type="python",
            original_search_type="smart",
            candidate_count=100,
            return_format="string",
            formatter=formatter,
        )
        assert isinstance(output, str)
        assert "Strategy:" in output
        assert "Files:" in output
