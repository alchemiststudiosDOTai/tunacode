"""Tests for glob helper functions in tunacode.tools.glob."""

import re

from tunacode.tools.glob import (
    EMPTY_EXCLUDE_DIR_PATTERNS,
    MAX_RESULTS,
    SortOrder,
    _compile_patterns,
    _entry_matches_any_pattern,
    _expand_brace_pattern,
    _format_output,
    _normalize_exclude_dir_patterns,
    _parse_sort_order,
    _single_pattern_matches,
)


class TestParseSortOrder:
    def test_valid_values(self):
        assert _parse_sort_order("modified") == SortOrder.MODIFIED
        assert _parse_sort_order("size") == SortOrder.SIZE
        assert _parse_sort_order("alphabetical") == SortOrder.ALPHABETICAL
        assert _parse_sort_order("depth") == SortOrder.DEPTH

    def test_invalid_falls_back_to_modified(self):
        assert _parse_sort_order("invalid") == SortOrder.MODIFIED
        assert _parse_sort_order("") == SortOrder.MODIFIED


class TestNormalizeExcludeDirPatterns:
    def test_none_returns_empty(self):
        assert _normalize_exclude_dir_patterns(None) == EMPTY_EXCLUDE_DIR_PATTERNS

    def test_empty_list_returns_empty(self):
        assert _normalize_exclude_dir_patterns([]) == EMPTY_EXCLUDE_DIR_PATTERNS

    def test_appends_slash_suffix(self):
        result = _normalize_exclude_dir_patterns(["node_modules"])
        assert result == ("node_modules/",)

    def test_preserves_existing_slash(self):
        result = _normalize_exclude_dir_patterns(["build/"])
        assert result == ("build/",)

    def test_strips_whitespace(self):
        result = _normalize_exclude_dir_patterns(["  dist  "])
        assert result == ("dist/",)

    def test_skips_blank_entries(self):
        result = _normalize_exclude_dir_patterns(["a", "", "  ", "b"])
        assert result == ("a/", "b/")

    def test_multiple_patterns(self):
        result = _normalize_exclude_dir_patterns(["node_modules", ".venv/", "dist"])
        assert result == ("node_modules/", ".venv/", "dist/")


class TestExpandBracePattern:
    def test_no_braces(self):
        assert _expand_brace_pattern("*.py") == ["*.py"]

    def test_simple_brace(self):
        result = _expand_brace_pattern("*.{py,js}")
        assert sorted(result) == sorted(["*.py", "*.js"])

    def test_multiple_options(self):
        result = _expand_brace_pattern("*.{py,js,ts}")
        assert sorted(result) == sorted(["*.py", "*.js", "*.ts"])

    def test_nested_braces(self):
        # Multiple brace groups require the stack to re-expand intermediate results.
        result = _expand_brace_pattern("{src,lib}.{py,js}")
        assert sorted(result) == sorted(["src.py", "src.js", "lib.py", "lib.js"])

    def test_prefix_and_suffix(self):
        result = _expand_brace_pattern("src/*.{py,js}.bak")
        assert sorted(result) == sorted(["src/*.py.bak", "src/*.js.bak"])

    def test_unmatched_brace_returns_as_is(self):
        assert _expand_brace_pattern("*.{py") == ["*.{py"]
        assert _expand_brace_pattern("*.py}") == ["*.py}"]

    def test_empty_string(self):
        assert _expand_brace_pattern("") == [""]


class TestCompilePatterns:
    def test_simple_pattern(self):
        compiled = _compile_patterns(["*.py"], 0)
        assert len(compiled) == 1
        pat_str, regex = compiled[0]
        assert pat_str == "*.py"
        assert regex.match("test.py")
        assert not regex.match("test.js")

    def test_double_star_pattern(self):
        compiled = _compile_patterns(["**/*.py"], 0)
        assert len(compiled) == 1
        _, regex = compiled[0]
        assert regex.match("src/main.py")

    def test_case_insensitive(self):
        compiled = _compile_patterns(["*.py"], re.IGNORECASE)
        _, regex = compiled[0]
        assert regex.match("test.PY")


class TestSinglePatternMatches:
    def test_simple_match(self):
        compiled = _compile_patterns(["*.py"], 0)
        _, comp = compiled[0]
        assert _single_pattern_matches("test.py", "test.py", "*.py", comp, recursive=True)

    def test_simple_no_match(self):
        compiled = _compile_patterns(["*.py"], 0)
        _, comp = compiled[0]
        assert not _single_pattern_matches("test.js", "test.js", "*.py", comp, recursive=True)

    def test_double_star_recursive(self):
        compiled = _compile_patterns(["**/*.py"], 0)
        _, comp = compiled[0]
        assert _single_pattern_matches("test.py", "src/test.py", "**/*.py", comp, recursive=True)

    def test_double_star_non_recursive_fallback(self):
        compiled = _compile_patterns(["**/*.py"], 0)
        _, comp = compiled[0]
        result = _single_pattern_matches("test.py", "test.py", "**/*.py", comp, recursive=False)
        assert result is True

    def test_double_star_fnmatch_fallback(self):
        compiled = _compile_patterns(["**/test_*.py"], 0)
        _, comp = compiled[0]
        result = _single_pattern_matches(
            "test_foo.py", "unmatched_dir", "**/test_*.py", comp, recursive=True
        )
        assert result is True


class TestEntryMatchesAnyPattern:
    def test_matches_one_pattern(self):
        compiled = _compile_patterns(["*.py", "*.js"], 0)
        assert _entry_matches_any_pattern("test.py", "test.py", compiled, recursive=True)
        assert _entry_matches_any_pattern("test.js", "test.js", compiled, recursive=True)

    def test_matches_none(self):
        compiled = _compile_patterns(["*.py"], 0)
        assert not _entry_matches_any_pattern("test.js", "test.js", compiled, recursive=True)


class TestFormatOutput:
    def test_single_file(self):
        output = _format_output("*.py", ["/a/b.py"], MAX_RESULTS)
        assert "Found 1 file" in output
        assert "/a/b.py" in output

    def test_multiple_files(self):
        output = _format_output("*.py", ["/a.py", "/b.py"], MAX_RESULTS)
        assert "Found 2 files" in output

    def test_truncation_message(self):
        matches = [f"/f{i}.py" for i in range(10)]
        output = _format_output("*.py", matches, 10)
        assert "(truncated at 10)" in output

    def test_no_truncation_when_under_limit(self):
        output = _format_output("*.py", ["/a.py"], MAX_RESULTS)
        assert "truncated" not in output

    def test_includes_pattern(self):
        output = _format_output("**/*.tsx", ["/a.tsx"], MAX_RESULTS)
        assert "**/*.tsx" in output


class TestSortOrder:
    def test_enum_values(self):
        assert SortOrder.MODIFIED.value == "modified"
        assert SortOrder.SIZE.value == "size"
        assert SortOrder.ALPHABETICAL.value == "alphabetical"
        assert SortOrder.DEPTH.value == "depth"
