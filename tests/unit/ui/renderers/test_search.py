"""Tests for search.py pure functions and parsers."""

from __future__ import annotations

from tunacode.ui.renderers.search import SearchDisplayRenderer, _paginate

# ---------------------------------------------------------------------------
# _paginate
# ---------------------------------------------------------------------------


class TestPaginate:
    """Generic list pagination."""

    def test_first_page_returns_correct_slice(self) -> None:
        items = list(range(20))
        page_items, start_idx, total_pages = _paginate(items, page=1, page_size=5)
        assert page_items == [0, 1, 2, 3, 4]
        assert start_idx == 0
        assert total_pages == 4

    def test_second_page(self) -> None:
        items = list(range(20))
        page_items, start_idx, total_pages = _paginate(items, page=2, page_size=5)
        assert page_items == [5, 6, 7, 8, 9]
        assert start_idx == 5
        assert total_pages == 4

    def test_last_page_partial(self) -> None:
        items = list(range(7))
        page_items, start_idx, total_pages = _paginate(items, page=2, page_size=5)
        assert page_items == [5, 6]
        assert start_idx == 5
        assert total_pages == 2

    def test_empty_list(self) -> None:
        page_items, start_idx, total_pages = _paginate([], page=1, page_size=5)
        assert page_items == []
        assert start_idx == 0
        assert total_pages == 1

    def test_page_beyond_range_returns_empty(self) -> None:
        items = list(range(5))
        page_items, _start_idx, total_pages = _paginate(items, page=10, page_size=5)
        assert page_items == []
        assert total_pages == 1

    def test_page_size_larger_than_list(self) -> None:
        items = [1, 2, 3]
        page_items, _start_idx, total_pages = _paginate(items, page=1, page_size=100)
        assert page_items == [1, 2, 3]
        assert total_pages == 1

    def test_single_item(self) -> None:
        page_items, start_idx, total_pages = _paginate(["a"], page=1, page_size=5)
        assert page_items == ["a"]
        assert start_idx == 0
        assert total_pages == 1


# ---------------------------------------------------------------------------
# SearchDisplayRenderer.parse_grep_output
# ---------------------------------------------------------------------------


GREP_OUTPUT_VALID = """\
Found 2 matches for pattern: test_func
\u2501\u2501\u2501
\U0001f4c1 src/main.py:5
\u25b6  5\u2502  def \u27e8test_func\u27e9()
\U0001f4c1 src/utils.py:12
\u25b6  12\u2502  result = \u27e8test_func\u27e9(args)"""

GREP_OUTPUT_SINGLE = """\
Found 1 match for pattern: hello
\U0001f4c1 app.py:1
\u25b6  1\u2502  print(\u27e8hello\u27e9)"""


class TestParseGrepOutput:
    """Parse grep tool output into SearchResultData."""

    def test_valid_output_parses_results(self) -> None:
        data = SearchDisplayRenderer.parse_grep_output(GREP_OUTPUT_VALID, "test_func")
        assert data is not None
        assert data.query == "test_func"
        assert data.total_count == 2
        assert len(data.results) == 2

    def test_valid_output_first_result(self) -> None:
        data = SearchDisplayRenderer.parse_grep_output(GREP_OUTPUT_VALID, "test_func")
        assert data is not None
        first = data.results[0]
        assert first["file"] == "src/main.py"
        assert first["line_number"] == 5
        assert "test_func" in first["snippet"]

    def test_valid_output_second_result(self) -> None:
        data = SearchDisplayRenderer.parse_grep_output(GREP_OUTPUT_VALID, "test_func")
        assert data is not None
        second = data.results[1]
        assert second["file"] == "src/utils.py"
        assert second["line_number"] == 12

    def test_empty_text_returns_none(self) -> None:
        assert SearchDisplayRenderer.parse_grep_output("", "query") is None

    def test_none_text_returns_none(self) -> None:
        assert SearchDisplayRenderer.parse_grep_output(None, "query") is None  # type: ignore[arg-type]

    def test_text_without_found_returns_none(self) -> None:
        assert SearchDisplayRenderer.parse_grep_output("no results here", "query") is None

    def test_bad_header_returns_none(self) -> None:
        text = "Found some stuff but no proper header\nrandom lines"
        assert SearchDisplayRenderer.parse_grep_output(text, "query") is None

    def test_query_fallback_to_detected(self) -> None:
        """When query is None, use the pattern from the header."""
        data = SearchDisplayRenderer.parse_grep_output(GREP_OUTPUT_VALID, None)
        assert data is not None
        assert data.query == "test_func"

    def test_single_match_singular_header(self) -> None:
        data = SearchDisplayRenderer.parse_grep_output(GREP_OUTPUT_SINGLE, "hello")
        assert data is not None
        assert data.total_count == 1
        assert len(data.results) == 1

    def test_header_only_no_file_matches_returns_none(self) -> None:
        """Header present but no file/match lines -> no results -> None."""
        text = "Found 5 matches for pattern: foo\n\nno file lines here"
        assert SearchDisplayRenderer.parse_grep_output(text, "foo") is None


# ---------------------------------------------------------------------------
# SearchDisplayRenderer.parse_glob_output
# ---------------------------------------------------------------------------


GLOB_OUTPUT_VALID = """\
Found 2 files matching pattern: *.py
./src/main.py
./src/utils.py"""

GLOB_OUTPUT_SINGLE = """\
Found 1 file matching pattern: *.rs
./src/lib.rs"""

GLOB_OUTPUT_WITH_SOURCE = """\
[source:index]
Found 3 files matching pattern: *.txt
./a.txt
./b.txt
./c.txt"""


class TestParseGlobOutput:
    """Parse glob tool output into SearchResultData."""

    def test_valid_output_parses_results(self) -> None:
        data = SearchDisplayRenderer.parse_glob_output(GLOB_OUTPUT_VALID, "*.py")
        assert data is not None
        assert data.query == "*.py"
        assert data.total_count == 2
        assert len(data.results) == 2

    def test_valid_output_first_result(self) -> None:
        data = SearchDisplayRenderer.parse_glob_output(GLOB_OUTPUT_VALID, "*.py")
        assert data is not None
        first = data.results[0]
        assert first["file"] == "./src/main.py"
        assert first["title"] == "./src/main.py"
        assert first["snippet"] == "main.py"

    def test_valid_output_second_result(self) -> None:
        data = SearchDisplayRenderer.parse_glob_output(GLOB_OUTPUT_VALID, "*.py")
        assert data is not None
        second = data.results[1]
        assert second["file"] == "./src/utils.py"
        assert second["snippet"] == "utils.py"

    def test_empty_text_returns_none(self) -> None:
        assert SearchDisplayRenderer.parse_glob_output("", "*.py") is None

    def test_text_without_found_returns_none(self) -> None:
        assert SearchDisplayRenderer.parse_glob_output("no results", "*.py") is None

    def test_pattern_fallback_to_detected(self) -> None:
        """When pattern is None, use the pattern from the header."""
        data = SearchDisplayRenderer.parse_glob_output(GLOB_OUTPUT_VALID, None)
        assert data is not None
        assert data.query == "*.py"

    def test_single_file_singular_header(self) -> None:
        data = SearchDisplayRenderer.parse_glob_output(GLOB_OUTPUT_SINGLE, "*.rs")
        assert data is not None
        assert data.total_count == 1
        assert len(data.results) == 1

    def test_source_marker_extracted(self) -> None:
        data = SearchDisplayRenderer.parse_glob_output(GLOB_OUTPUT_WITH_SOURCE, "*.txt")
        assert data is not None
        assert data.source == "index"
        assert data.total_count == 3
        assert len(data.results) == 3

    def test_no_source_marker_source_is_none(self) -> None:
        data = SearchDisplayRenderer.parse_glob_output(GLOB_OUTPUT_VALID, "*.py")
        assert data is not None
        assert data.source is None

    def test_header_only_no_paths_returns_none(self) -> None:
        """Header present but no file paths -> no results -> None."""
        text = "Found 3 files matching pattern: *.py\n\n"
        assert SearchDisplayRenderer.parse_glob_output(text, "*.py") is None

    def test_none_text_returns_none(self) -> None:
        assert SearchDisplayRenderer.parse_glob_output(None, "*.py") is None  # type: ignore[arg-type]
