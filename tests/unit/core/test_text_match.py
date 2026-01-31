"""Tests for update_file tool and text matching."""

import time
from pathlib import Path

import pytest

from tunacode.tools.update_file import update_file


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

        from tunacode.exceptions import ToolRetryError

        start = time.perf_counter()
        with pytest.raises(ToolRetryError, match="not found"):
            await update_file(str(filepath), "def nonexistent():\n    pass", "x")
        elapsed = time.perf_counter() - start

        # Without fail-fast: would take 10+ seconds
        # With fail-fast: should be < 0.5s
        assert elapsed < 1.0, f"Took {elapsed:.2f}s - fail-fast may be broken"


class TestReplaceDirectly:
    """Test replace() function directly - no file I/O, no LSP."""

    def test_replace_is_fast(self):
        """Verify replace() itself is fast."""
        from tunacode.tools.utils.text_match import replace

        content = "class Foo:\n    def bar(self):\n        pass\n"
        target = "def bar(self):\n    pass"
        replacement = "def bar(self):\n    return 42"

        start = time.perf_counter()
        result = replace(content, target, replacement)
        elapsed = time.perf_counter() - start

        assert "return 42" in result
        assert elapsed < 0.01, f"replace() took {elapsed:.4f}s - should be instant"
