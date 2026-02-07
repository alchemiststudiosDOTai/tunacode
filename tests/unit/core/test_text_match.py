"""Tests for update_file tool and text matching."""

import time
from pathlib import Path

import pytest

from tunacode.tools.update_file import update_file
from tunacode.tools.utils.text_match import (
    MIN_ANCHOR_DISTANCE,
    MIN_ANCHOR_LINES,
    _find_anchor_candidates,
    _line_similarity,
    _min_indentation,
    _prepare_search_lines,
    _remove_indentation,
    _trim_trailing_empty_line,
    _try_replace_all,
    _try_replace_unique,
    block_anchor_replacer,
    indentation_flexible_replacer,
    levenshtein,
    line_trimmed_replacer,
    replace,
    simple_replacer,
)


class TestTextMatchReplacers:
    """Test the fuzzy text matching in update_file."""

    async def test_exact_match(self, tmp_path: Path, mock_no_xml_prompt):
        """Exact string match - simple_replacer."""
        code = "def foo():\n    return 1\n"
        filepath = tmp_path / "test.py"
        filepath.write_text(code)

        result = await update_file(
            str(filepath),
            "def foo():\n    return 1",
            "def foo():\n    return 42",
        )

        assert "updated successfully" in result
        assert "return 42" in filepath.read_text()

    async def test_wrong_indentation(self, tmp_path: Path, mock_no_xml_prompt):
        """Wrong indentation level - indentation_flexible_replacer."""
        code = "class Foo:\n    def bar(self):\n        pass\n"
        filepath = tmp_path / "test.py"
        filepath.write_text(code)

        # Target has 0-space indent, file has 4-space
        result = await update_file(
            str(filepath),
            "def bar(self):\n    pass",
            "def bar(self):\n    return 42",
        )

        assert "updated successfully" in result
        assert "return 42" in filepath.read_text()

    async def test_trailing_whitespace(self, tmp_path: Path, mock_no_xml_prompt):
        """Trailing whitespace mismatch - line_trimmed_replacer."""
        code = "def foo():   \n    return 1   \n"  # trailing spaces
        filepath = tmp_path / "test.py"
        filepath.write_text(code)

        # Target has no trailing spaces
        result = await update_file(
            str(filepath),
            "def foo():\n    return 1",
            "def foo():\n    return 42",
        )

        assert "updated successfully" in result
        assert "return 42" in filepath.read_text()

    async def test_fuzzy_anchor_match(self, tmp_path: Path, mock_no_xml_prompt):
        """Middle lines differ slightly - block_anchor_replacer."""
        code = "def calc():\n    x = compute_value()\n    return x\n"
        filepath = tmp_path / "test.py"
        filepath.write_text(code)

        # Middle line slightly different
        result = await update_file(
            str(filepath),
            "def calc():\n    x = compute()\n    return x",
            "def calc():\n    return 42",
        )

        assert "updated successfully" in result
        assert "return 42" in filepath.read_text()

    async def test_large_file_performance(self, tmp_path: Path, mock_no_xml_prompt):
        """Large file completes fast - verifies fail-fast optimization."""
        lines = [f"    x{i} = {i}" for i in range(2000)]
        code = "class Config:\n" + "\n".join(lines) + "\n"
        filepath = tmp_path / "large.py"
        filepath.write_text(code)

        from pydantic_ai.exceptions import ModelRetry

        start = time.perf_counter()
        with pytest.raises(ModelRetry, match="not found"):
            await update_file(str(filepath), "def nonexistent():\n    pass", "x")
        elapsed = time.perf_counter() - start

        # Without fail-fast: would take 10+ seconds
        # With fail-fast: should be < 0.5s
        assert elapsed < 1.0, f"Took {elapsed:.2f}s - fail-fast may be broken"


class TestReplaceDirectly:
    """Test replace() function directly - no file I/O, no LSP."""

    def test_replace_is_fast(self):
        """Verify replace() itself is fast."""
        content = "class Foo:\n    def bar(self):\n        pass\n"
        target = "def bar(self):\n    pass"
        replacement = "def bar(self):\n    return 42"

        start = time.perf_counter()
        result = replace(content, target, replacement)
        elapsed = time.perf_counter() - start

        assert "return 42" in result
        assert elapsed < 0.01, f"replace() took {elapsed:.4f}s - should be instant"


class TestLevenshtein:
    def test_identical_strings(self):
        assert levenshtein("abc", "abc") == 0

    def test_empty_first(self):
        assert levenshtein("", "abc") == 3

    def test_empty_second(self):
        assert levenshtein("abc", "") == 3

    def test_both_empty(self):
        assert levenshtein("", "") == 0

    def test_single_substitution(self):
        assert levenshtein("cat", "bat") == 1

    def test_single_insertion(self):
        assert levenshtein("cat", "cats") == 1

    def test_single_deletion(self):
        assert levenshtein("cats", "cat") == 1

    def test_completely_different(self):
        assert levenshtein("abc", "xyz") == 3


class TestSimpleReplacer:
    def test_exact_match_yields(self):
        results = list(simple_replacer("hello world", "hello"))
        assert results == ["hello"]

    def test_no_match_empty(self):
        results = list(simple_replacer("hello world", "goodbye"))
        assert results == []

    def test_empty_find_always_matches(self):
        # Python substring semantics: "" in "hello" == True
        results = list(simple_replacer("hello", ""))
        assert results == [""]


class TestLineTrimmedReplacer:
    def test_whitespace_match(self):
        content = "  def foo():  \n    return 1  \n"
        find = "def foo():\n    return 1"
        results = list(line_trimmed_replacer(content, find))
        assert len(results) == 1

    def test_no_match(self):
        content = "def bar():\n    pass\n"
        find = "def foo():\n    pass"
        results = list(line_trimmed_replacer(content, find))
        assert results == []

    def test_empty_find_returns_nothing(self):
        results = list(line_trimmed_replacer("hello\n", ""))
        assert results == []

    def test_trailing_empty_line_stripped(self):
        content = "def foo():\n    pass\n"
        find = "def foo():\n    pass\n"
        results = list(line_trimmed_replacer(content, find))
        assert len(results) == 1


class TestIndentationFlexibleReplacer:
    def test_different_indent_matches(self):
        content = "    def foo():\n        return 1\n"
        find = "def foo():\n    return 1"
        results = list(indentation_flexible_replacer(content, find))
        assert len(results) == 1

    def test_no_match(self):
        content = "def bar():\n    pass\n"
        find = "def foo():\n    pass"
        results = list(indentation_flexible_replacer(content, find))
        assert results == []

    def test_empty_find_returns_nothing(self):
        results = list(indentation_flexible_replacer("hello\n", ""))
        assert results == []


class TestBlockAnchorReplacer:
    def test_fuzzy_middle_match(self):
        content = "def calc():\n    x = compute_value()\n    return x\n"
        find = "def calc():\n    x = compute()\n    return x"
        results = list(block_anchor_replacer(content, find))
        assert len(results) == 1

    def test_too_few_lines_returns_empty(self):
        content = "one line\n"
        find = "one line"
        results = list(block_anchor_replacer(content, find))
        assert results == []

    def test_no_anchor_match(self):
        content = "def foo():\n    pass\n    done\n"
        find = "def bar():\n    pass\n    done"
        results = list(block_anchor_replacer(content, find))
        assert results == []


class TestHelperFunctions:
    def test_remove_indentation_basic(self):
        text = "    hello\n    world"
        assert _remove_indentation(text) == "hello\nworld"

    def test_remove_indentation_mixed(self):
        text = "    hello\n        world"
        assert _remove_indentation(text) == "hello\n    world"

    def test_remove_indentation_no_indent(self):
        text = "hello\nworld"
        assert _remove_indentation(text) == "hello\nworld"

    def test_remove_indentation_all_empty(self):
        text = "  \n  "
        assert _remove_indentation(text) == "  \n  "

    def test_min_indentation_basic(self):
        assert _min_indentation(["    a", "      b"]) == 4

    def test_min_indentation_no_indent(self):
        assert _min_indentation(["a", "b"]) == 0

    def test_min_indentation_empty_list(self):
        assert _min_indentation([]) == 0

    def test_trim_trailing_empty_line_with_empty(self):
        assert _trim_trailing_empty_line(["a", "b", ""]) == ["a", "b"]

    def test_trim_trailing_empty_line_without_empty(self):
        assert _trim_trailing_empty_line(["a", "b"]) == ["a", "b"]

    def test_trim_trailing_empty_line_empty_list(self):
        assert _trim_trailing_empty_line([]) == []

    def test_prepare_search_lines_too_short(self):
        too_short = "\n".join(f"line{i}" for i in range(MIN_ANCHOR_LINES - 1))
        assert _prepare_search_lines(too_short) is None

    def test_prepare_search_lines_valid(self):
        valid = "\n".join(f"line{i}" for i in range(MIN_ANCHOR_LINES))
        result = _prepare_search_lines(valid)
        assert result == [f"line{i}" for i in range(MIN_ANCHOR_LINES)]

    def test_line_similarity_identical(self):
        assert _line_similarity("hello", "hello") == 1.0

    def test_line_similarity_completely_different(self):
        sim = _line_similarity("abc", "xyz")
        assert sim is not None
        assert sim == 0.0

    def test_line_similarity_both_empty(self):
        assert _line_similarity("", "") is None

    def test_find_anchor_candidates_basic(self):
        # Build lines so end - start >= MIN_ANCHOR_DISTANCE
        middle_lines = [f"middle{i}\n" for i in range(MIN_ANCHOR_DISTANCE - 1)]
        lines = ["first\n", *middle_lines, "last\n"]
        last_index = len(lines) - 1
        result = _find_anchor_candidates(lines, "first", "last")
        assert len(result) == 1
        assert result[0] == (0, last_index)

    def test_find_anchor_candidates_no_match(self):
        lines = ["a\n", "b\n", "c\n"]
        result = _find_anchor_candidates(lines, "x", "y")
        assert result == []

    def test_try_replace_all_exact(self):
        result = _try_replace_all("aXa", "X", "Y", is_exact=True)
        assert result == "aYa"

    def test_try_replace_all_non_exact_returns_none(self):
        assert _try_replace_all("aXa", "X", "Y", is_exact=False) is None

    def test_try_replace_unique_single_occurrence(self):
        result = _try_replace_unique("aXb", "X", "Y")
        assert result == "aYb"

    def test_try_replace_unique_multiple_returns_none(self):
        assert _try_replace_unique("aXbXc", "X", "Y") is None

    def test_try_replace_unique_not_found_returns_none(self):
        assert _try_replace_unique("abc", "X", "Y") is None


class TestReplaceSuccess:
    def test_replace_all_exact(self):
        result = replace("aXbXc", "X", "Y", replace_all=True)
        assert result == "aYbYc"

    def test_replace_unique_match(self):
        result = replace("hello X world", "X", "Y")
        assert result == "hello Y world"


class TestReplaceErrors:
    def test_empty_old_string_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            replace("content", "", "new")

    def test_same_old_new_raises(self):
        with pytest.raises(ValueError, match="must be different"):
            replace("content", "same", "same")

    def test_not_found_raises(self):
        with pytest.raises(ValueError, match="not found"):
            replace("hello world", "goodbye universe", "something")
