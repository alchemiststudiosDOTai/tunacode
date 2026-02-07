"""Unit tests for pure helper functions in diagnostics renderer."""

from __future__ import annotations

from tunacode.ui.renderers.tools.diagnostics import (
    DiagnosticItem,
    DiagnosticsData,
    extract_diagnostics_from_result,
    parse_diagnostics_block,
)

# ---------------------------------------------------------------------------
# DiagnosticItem / DiagnosticsData dataclass smoke tests
# ---------------------------------------------------------------------------


class TestDiagnosticItem:
    """Verify DiagnosticItem dataclass behaviour."""

    def test_fields_stored(self) -> None:
        item = DiagnosticItem(severity="error", line=42, message="bad type")
        assert item.severity == "error"
        assert item.line == 42
        assert item.message == "bad type"

    def test_equality(self) -> None:
        a = DiagnosticItem(severity="warning", line=1, message="unused")
        b = DiagnosticItem(severity="warning", line=1, message="unused")
        assert a == b


class TestDiagnosticsData:
    """Verify DiagnosticsData dataclass behaviour."""

    def test_fields_stored(self) -> None:
        item = DiagnosticItem(severity="error", line=10, message="msg")
        data = DiagnosticsData(items=[item], error_count=1, warning_count=0, info_count=0)
        assert len(data.items) == 1
        assert data.error_count == 1
        assert data.warning_count == 0
        assert data.info_count == 0


# ---------------------------------------------------------------------------
# parse_diagnostics_block
# ---------------------------------------------------------------------------


class TestParseDiagnosticsBlock:
    """Tests for parse_diagnostics_block()."""

    # -- None / empty inputs ------------------------------------------------

    def test_empty_string_returns_none(self) -> None:
        assert parse_diagnostics_block("") is None

    def test_no_tags_returns_none(self) -> None:
        assert parse_diagnostics_block("just plain text") is None

    def test_empty_tags_returns_none(self) -> None:
        content = "<file_diagnostics></file_diagnostics>"
        assert parse_diagnostics_block(content) is None

    def test_whitespace_only_inside_tags_returns_none(self) -> None:
        content = "<file_diagnostics>   \n  \n  </file_diagnostics>"
        assert parse_diagnostics_block(content) is None

    # -- Single diagnostic lines -------------------------------------------

    def test_single_error(self) -> None:
        content = (
            "<file_diagnostics>\nError (line 10): Type mismatch in assignment\n</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 1
        assert result.items[0].severity == "error"
        assert result.items[0].line == 10
        assert result.items[0].message == "Type mismatch in assignment"
        assert result.error_count == 1
        assert result.warning_count == 0
        assert result.info_count == 0

    def test_single_warning(self) -> None:
        content = "<file_diagnostics>\nWarning (line 5): Unused variable 'x'\n</file_diagnostics>"
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 1
        assert result.items[0].severity == "warning"
        assert result.items[0].line == 5
        assert result.warning_count == 1
        assert result.error_count == 0
        assert result.info_count == 0

    def test_single_info(self) -> None:
        content = (
            "<file_diagnostics>\nInfo (line 1): Consider using walrus operator\n</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert result.items[0].severity == "info"
        assert result.info_count == 1

    def test_single_hint(self) -> None:
        content = "<file_diagnostics>\nHint (line 99): Unnecessary parentheses\n</file_diagnostics>"
        result = parse_diagnostics_block(content)
        assert result is not None
        assert result.items[0].severity == "hint"
        # Hint counts toward info_count (the else branch)
        assert result.info_count == 1
        assert result.error_count == 0
        assert result.warning_count == 0

    # -- Multiple diagnostics ----------------------------------------------

    def test_mixed_severities(self) -> None:
        content = (
            "<file_diagnostics>\n"
            "Error (line 10): Type mismatch\n"
            "Warning (line 15): Unused import\n"
            "Error (line 20): Missing return\n"
            "Info (line 30): Consider refactoring\n"
            "</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 4
        assert result.error_count == 2
        assert result.warning_count == 1
        assert result.info_count == 1

    def test_items_preserve_order(self) -> None:
        content = (
            "<file_diagnostics>\n"
            "Warning (line 3): first\n"
            "Error (line 1): second\n"
            "</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert result.items[0].message == "first"
        assert result.items[1].message == "second"

    # -- Summary line is skipped -------------------------------------------

    def test_summary_line_ignored(self) -> None:
        content = (
            "<file_diagnostics>\n"
            "Error (line 10): Bad thing\n"
            "Summary: 1 error found\n"
            "</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 1

    # -- Case-insensitive severity matching --------------------------------

    def test_case_insensitive_severity(self) -> None:
        content = (
            "<file_diagnostics>\n"
            "ERROR (line 1): upper\n"
            "warning (line 2): lower\n"
            "Info (line 3): mixed\n"
            "</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 3
        # Severities are lowered
        assert result.items[0].severity == "error"
        assert result.items[1].severity == "warning"
        assert result.items[2].severity == "info"

    # -- Malformed lines ---------------------------------------------------

    def test_malformed_lines_skipped(self) -> None:
        content = (
            "<file_diagnostics>\n"
            "This is not a diagnostic\n"
            "Error (line 10): Valid one\n"
            "random garbage\n"
            "</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 1
        assert result.items[0].message == "Valid one"

    def test_all_malformed_returns_none(self) -> None:
        content = "<file_diagnostics>\nnot a diagnostic\nalso not a diagnostic\n</file_diagnostics>"
        assert parse_diagnostics_block(content) is None

    # -- Content surrounding the tags --------------------------------------

    def test_surrounding_text_ignored(self) -> None:
        content = (
            "Some prefix text\n"
            "<file_diagnostics>\n"
            "Error (line 7): found it\n"
            "</file_diagnostics>\n"
            "Some suffix text"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 1
        assert result.items[0].line == 7

    # -- Blank lines inside block ------------------------------------------

    def test_blank_lines_inside_block_ignored(self) -> None:
        content = (
            "<file_diagnostics>\n"
            "\n"
            "Error (line 1): alpha\n"
            "\n"
            "\n"
            "Warning (line 2): beta\n"
            "\n"
            "</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert len(result.items) == 2

    # -- Large line numbers ------------------------------------------------

    def test_large_line_number(self) -> None:
        content = "<file_diagnostics>\nError (line 999999): deep in the file\n</file_diagnostics>"
        result = parse_diagnostics_block(content)
        assert result is not None
        assert result.items[0].line == 999999

    # -- Message with special characters -----------------------------------

    def test_message_with_colons(self) -> None:
        content = (
            "<file_diagnostics>\nError (line 5): expected type: int, got: str\n</file_diagnostics>"
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert result.items[0].message == "expected type: int, got: str"

    def test_message_with_quotes(self) -> None:
        content = (
            '<file_diagnostics>\nError (line 5): variable "foo" is undefined\n</file_diagnostics>'
        )
        result = parse_diagnostics_block(content)
        assert result is not None
        assert result.items[0].message == 'variable "foo" is undefined'


# ---------------------------------------------------------------------------
# extract_diagnostics_from_result
# ---------------------------------------------------------------------------


class TestExtractDiagnosticsFromResult:
    """Tests for extract_diagnostics_from_result()."""

    # -- No diagnostics present --------------------------------------------

    def test_no_diagnostics_tag(self) -> None:
        text = "File updated successfully."
        result_text, block = extract_diagnostics_from_result(text)
        assert result_text == "File updated successfully."
        assert block is None

    def test_empty_input(self) -> None:
        result_text, block = extract_diagnostics_from_result("")
        assert result_text == ""
        assert block is None

    # -- Diagnostics present -----------------------------------------------

    def test_extracts_block_and_cleans_result(self) -> None:
        diag_block = "<file_diagnostics>\nError (line 10): Bad thing\n</file_diagnostics>"
        original = f"File updated successfully.\n{diag_block}\nDone."
        result_text, block = extract_diagnostics_from_result(original)
        assert block == diag_block
        assert "<file_diagnostics>" not in result_text
        assert "File updated successfully." in result_text
        assert "Done." in result_text

    def test_result_is_stripped(self) -> None:
        """After removal, leading/trailing whitespace is stripped."""
        diag_block = "<file_diagnostics>\nWarning (line 1): w\n</file_diagnostics>"
        original = f"  {diag_block}  "
        result_text, block = extract_diagnostics_from_result(original)
        assert block is not None
        # The remaining text (empty after stripping) should be empty string
        assert result_text == ""

    def test_only_diagnostics_block(self) -> None:
        diag_block = "<file_diagnostics>\nError (line 1): oops\n</file_diagnostics>"
        result_text, block = extract_diagnostics_from_result(diag_block)
        assert block == diag_block
        assert result_text == ""

    def test_diagnostics_at_start(self) -> None:
        diag_block = "<file_diagnostics>\nError (line 1): oops\n</file_diagnostics>"
        original = f"{diag_block}\nFile written."
        result_text, block = extract_diagnostics_from_result(original)
        assert block == diag_block
        assert result_text == "File written."

    def test_diagnostics_at_end(self) -> None:
        diag_block = "<file_diagnostics>\nError (line 1): oops\n</file_diagnostics>"
        original = f"File written.\n{diag_block}"
        result_text, block = extract_diagnostics_from_result(original)
        assert block == diag_block
        assert result_text == "File written."

    def test_multiline_diagnostics_block(self) -> None:
        diag_block = (
            "<file_diagnostics>\n"
            "Error (line 10): first\n"
            "Warning (line 20): second\n"
            "Info (line 30): third\n"
            "</file_diagnostics>"
        )
        original = f"Prefix.\n{diag_block}\nSuffix."
        result_text, block = extract_diagnostics_from_result(original)
        assert block == diag_block
        assert "Prefix." in result_text
        assert "Suffix." in result_text

    # -- Roundtrip: extract then parse -------------------------------------

    def test_multiple_diagnostics_blocks(self) -> None:
        """When two diagnostics blocks exist, only the first is extracted."""
        block1 = "<file_diagnostics>\nError (line 1): first block error\n</file_diagnostics>"
        block2 = "<file_diagnostics>\nWarning (line 2): second block warning\n</file_diagnostics>"
        original = f"Prefix.\n{block1}\nMiddle.\n{block2}\nSuffix."
        result_text, block = extract_diagnostics_from_result(original)
        assert block is not None
        assert "first block error" in block
        assert "<file_diagnostics>" not in result_text or "second block warning" in result_text

    def test_roundtrip_extract_then_parse(self) -> None:
        """The block returned by extract can be fed into parse."""
        diag_block = (
            "<file_diagnostics>\n"
            "Error (line 10): Type mismatch\n"
            "Warning (line 20): Unused variable\n"
            "</file_diagnostics>"
        )
        original = f"Updated file.\n{diag_block}"
        _, block = extract_diagnostics_from_result(original)
        assert block is not None

        data = parse_diagnostics_block(block)
        assert data is not None
        assert data.error_count == 1
        assert data.warning_count == 1
        assert len(data.items) == 2
